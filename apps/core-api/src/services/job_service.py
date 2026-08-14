"""Job description CRUD (form-created jobs; no JD file/text parse)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.enums import JobStatus, UserRole
from src.models.job_description import JobDescription
from src.models.organization import Organization
from src.models.user import User
from src.schemas.job import JobCreate, JobUpdate

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


def create_job(
    db: Session,
    *,
    organization_id: UUID,
    created_by: UUID,
    data: JobCreate,
) -> JobDescription:
    _assert_org_active(db, organization_id)
    payload = data.model_dump(exclude={"organization_id"})
    job = JobDescription(
        organization_id=organization_id,
        created_by=created_by,
        **payload,
    )
    _apply_status_timestamps(job, job.status)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job: JobDescription, data: JobUpdate) -> JobDescription:
    payload = data.model_dump(exclude_unset=True)
    new_status = payload.get("status")
    for key, value in payload.items():
        setattr(job, key, value)
    if new_status is not None:
        _apply_status_timestamps(job, new_status)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
