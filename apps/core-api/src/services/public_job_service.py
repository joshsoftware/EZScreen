"""Public job listing & detail query service for candidate portal."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.enums import (
    ApplicationSource,
    ApplicationStatus,
    JobStatus,
    JobType,
    TimelineActorType,
    TimelineEventType,
    UserRole,
    UserStatus,
    WorkType,
)
from src.models.job_description import JobDescription
from src.models.organization import Organization
from src.models.user import User
from src.schemas.public_job import (
    PublicCandidateApplyRequest,
    PublicCandidateApplyResponse,
    PublicJobListItem,
    PublicJobResponse,
)
from src.services import storage_service
from src.services.application_ingest_service import find_or_create_candidate
from src.services.application_timeline_service import append_timeline_event

__all__ = [
    "list_public_jobs",
    "get_public_job",
    "submit_public_application",
    "extract_subdomain_from_host",
]

_RESERVED_SUBDOMAINS = {"www", "api", "app", "localhost", "admin", "dashboard", "127"}


def extract_subdomain_from_host(host_header: str | None) -> str | None:
    """Extract organization subdomain from HTTP Host or X-Forwarded-Host header."""
    if not host_header:
        return None
    hostname = host_header.split(":")[0].strip().lower()
    parts = hostname.split(".")
    if len(parts) >= 2:
        subdomain = parts[0]
        if subdomain not in _RESERVED_SUBDOMAINS and not subdomain.isdigit():
            return subdomain
    return None


def list_public_jobs(
    db: Session,
    *,
    org_subdomain: str | None = None,
    search: str | None = None,
    job_type: JobType | None = None,
    work_type: WorkType | None = None,
    page: int = 1,
    limit: int = 20,
) -> list[PublicJobListItem]:
    stmt = (
        select(JobDescription, Organization)
        .join(Organization, JobDescription.organization_id == Organization.id)
        .where(
            JobDescription.status == JobStatus.published,
            Organization.is_active.is_(True),
        )
        .order_by(
            JobDescription.published_at.desc().nullslast(),
            JobDescription.created_at.desc(),
        )
    )

    if org_subdomain:
        stmt = stmt.where(func.lower(Organization.domain) == org_subdomain.strip().lower())

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            JobDescription.title.ilike(pattern)
            | JobDescription.location.ilike(pattern)
            | JobDescription.description.ilike(pattern)
        )

    if job_type:
        stmt = stmt.where(JobDescription.job_type == job_type)

    if work_type:
        stmt = stmt.where(JobDescription.work_type == work_type)

    offset = max(page - 1, 0) * limit
    stmt = stmt.offset(offset).limit(min(limit, 50))

    results = db.execute(stmt).all()

    items: list[PublicJobListItem] = []
    for job, org in results:
        items.append(
            PublicJobListItem(
                id=job.id,
                organization_id=job.organization_id,
                organization_name=org.name,
                organization_domain=org.domain,
                organization_logo_url=org.logo_url,
                title=job.title,
                job_type=job.job_type,
                work_type=job.work_type,
                location=job.location,
                experience_min=job.experience_min,
                experience_max=job.experience_max,
                skills=job.skills,
                created_at=job.created_at,
                published_at=job.published_at,
            )
        )
    return items


def get_public_job(
    db: Session,
    *,
    job_id: UUID,
    org_subdomain: str | None = None,
) -> PublicJobResponse | None:
    stmt = (
        select(JobDescription, Organization)
        .join(Organization, JobDescription.organization_id == Organization.id)
        .where(
            JobDescription.id == job_id,
            JobDescription.status == JobStatus.published,
            Organization.is_active.is_(True),
        )
    )

    if org_subdomain:
        stmt = stmt.where(func.lower(Organization.domain) == org_subdomain.strip().lower())

    row = db.execute(stmt).first()
    if row is None:
        return None

    job, org = row
    return PublicJobResponse(
        id=job.id,
        organization_id=job.organization_id,
        organization_name=org.name,
        organization_domain=org.domain,
        organization_logo_url=org.logo_url,
        title=job.title,
        description=job.description,
        job_type=job.job_type,
        work_type=job.work_type,
        location=job.location,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        skills=job.skills,
        parsed_jd=job.parsed_jd,
        created_at=job.created_at,
        published_at=job.published_at,
    )


def submit_public_application(
    db: Session,
    *,
    job_id: UUID,
    data: PublicCandidateApplyRequest,
) -> PublicCandidateApplyResponse:
    job = db.get(JobDescription, job_id)
    if job is None or job.status != JobStatus.published:
        raise LookupError("Job not found or no longer accepting applications")

    storage_service.validate_resume_s3_key(
        data.s3_key,
        organization_id=job.organization_id,
        job_id=job.id,
    )

    personal = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "phone": data.phone,
        "email": data.email,
    }
    candidate = find_or_create_candidate(db, data.email, personal)

    existing_app = db.scalar(
        select(Application).where(
            Application.job_description_id == job.id,
            Application.candidate_id == candidate.id,
        )
    )
    if existing_app is not None:
        raise ValueError("ALREADY_APPLIED")

    now = datetime.now(timezone.utc)
    application = Application(
        job_description_id=job.id,
        candidate_id=candidate.id,
        resume_url=data.s3_key,
        status=ApplicationStatus.applied,
        source=ApplicationSource.candidate,
        applied_at=now,
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ValueError("ALREADY_APPLIED") from exc

    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.applied,
        actor_type=TimelineActorType.system,
        to_status=ApplicationStatus.applied,
    )
    db.commit()
    db.refresh(application)

    return PublicCandidateApplyResponse(
        id=application.id,
        job_description_id=application.job_description_id,
        candidate_id=application.candidate_id,
        status=application.status.value,
        applied_at=application.applied_at,
        message="Application submitted successfully",
    )

