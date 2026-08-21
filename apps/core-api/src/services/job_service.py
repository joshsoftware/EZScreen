"""Job description CRUD. Form fields are sent to AI parse/jd; parsed_jd is stored on the job."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.config.settings import settings
from src.models.enums import JobStatus, UserRole
from src.models.job_description import JobDescription
from src.models.organization import Organization
from src.models.user import User
from src.schemas.job import JobCreate, JobSkills, JobUpdate

_JD_PARSE_FIELDS = (
    "title",
    "description",
    "job_type",
    "work_type",
    "location",
    "experience_min",
    "experience_max",
)

__all__ = [
    "list_jobs",
    "get_job",
    "create_job",
    "update_job",
    "resolve_organization_id",
]


def resolve_organization_id(user: User, requested: UUID | None) -> UUID:
    """Return the org to operate on. Super admin must pass organization_id."""
    if user.role == UserRole.super_admin:
        if requested is None:
            raise ValueError("organization_id is required for super_admin")
        return requested
    if user.organization_id is None:
        raise ValueError("User is not bound to an organization")
    if requested is not None and requested != user.organization_id:
        raise PermissionError("Cannot access another organization")
    return user.organization_id


def list_jobs(
    db: Session,
    *,
    organization_id: UUID,
    status: JobStatus | None = None,
    page: int = 1,
    limit: int = 20,
) -> list[JobDescription]:
    stmt = (
        select(JobDescription)
        .where(JobDescription.organization_id == organization_id)
        .options(selectinload(JobDescription.applications))
        .order_by(JobDescription.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(JobDescription.status == status)
    offset = max(page - 1, 0) * limit
    stmt = stmt.offset(offset).limit(min(limit, 50))
    return list(db.scalars(stmt).all())


def get_job(db: Session, job_id: UUID) -> JobDescription | None:
    return db.get(JobDescription, job_id)


def _assert_org_active(db: Session, organization_id: UUID) -> None:
    org = db.get(Organization, organization_id)
    if org is None:
        raise LookupError("Organization not found")
    if not org.is_active:
        raise ValueError("Cannot manage jobs for a suspended organization")


def _apply_status_timestamps(job: JobDescription, new_status: JobStatus) -> None:
    now = datetime.now(timezone.utc)
    if new_status == JobStatus.published and job.published_at is None:
        job.published_at = now
        job.closed_at = None
    if new_status == JobStatus.closed:
        job.closed_at = now
    if new_status == JobStatus.draft:
        job.closed_at = None


def _skills_dict(skills: JobSkills | dict | None) -> dict | None:
    if skills is None:
        return None
    if isinstance(skills, JobSkills):
        return skills.model_dump()
    if isinstance(skills, dict):
        return JobSkills.model_validate(skills).model_dump()
    return None


def _apply_skills(job: JobDescription, skills: JobSkills | dict | None) -> None:
    payload = _skills_dict(skills)
    job.skills = payload
    parsed = dict(job.parsed_jd) if isinstance(job.parsed_jd, dict) else {}
    if payload is not None:
        parsed["skills"] = payload
        job.parsed_jd = parsed


def create_job(
    db: Session,
    *,
    organization_id: UUID,
    created_by: UUID,
    data: JobCreate,
) -> JobDescription:
    _assert_org_active(db, organization_id)
    payload = data.model_dump(exclude={"organization_id", "skills"})
    parsed_jd = _call_parse_jd(data)
    job = JobDescription(
        organization_id=organization_id,
        created_by=created_by,
        parsed_jd=parsed_jd,
        **payload,
    )
    if data.skills is not None:
        _apply_skills(job, data.skills)
    _apply_status_timestamps(job, job.status)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job: JobDescription, data: JobUpdate) -> JobDescription:
    payload = data.model_dump(exclude_unset=True)
    skills = payload.pop("skills", None)
    skills_set = "skills" in data.model_fields_set
    new_status = payload.get("status")
    for key, value in payload.items():
        setattr(job, key, value)
    if new_status is not None:
        _apply_status_timestamps(job, new_status)
    if any(field in payload for field in _JD_PARSE_FIELDS):
        job.parsed_jd = _call_parse_jd(job)
    if skills_set:
        _apply_skills(job, skills)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def _html_to_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"(?i)<br\s*/?>", "\n", value)
    text = re.sub(r"(?i)</(p|div|h[1-6]|li)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def _jd_parse_body(source: JobCreate | JobDescription) -> dict:
    return {
        "title": source.title,
        "description": _html_to_text(source.description) or source.description,
        "job_type": _enum_value(source.job_type),
        "work_type": _enum_value(source.work_type),
        "location": source.location,
        "experience_min": source.experience_min,
        "experience_max": source.experience_max,
        "status": _enum_value(source.status),
    }


def _call_parse_jd(source: JobCreate | JobDescription) -> dict:
    url = f"{settings.parsing_service_url.rstrip('/')}/parse/jd"
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=_jd_parse_body(source))
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"JD parsing service unavailable: {exc}") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response from JD parsing service")
    if data.get("status") != "success":
        raise ValueError(data.get("error_message") or "JD parsing did not succeed")
    parsed_jd = data.get("parsed_jd")
    if not isinstance(parsed_jd, dict):
        raise ValueError("JD parse response missing parsed_jd")
    return parsed_jd
