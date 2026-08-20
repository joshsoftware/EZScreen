"""Job description routes (HR / Org Admin / Super Admin)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import DbSession, require_roles
from src.models.enums import JobStatus, UserRole
from src.models.user import User
from src.schemas.job import (
    JobCreate,
    JobListItem,
    JobResponse,
    JobUpdate,
    JobUpdateResponse,
)
from src.services import job_service

router = APIRouter(prefix="/jobs", tags=["Job Descriptions"])

JobActor = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.hr, UserRole.organization_admin, UserRole.super_admin
        )
    ),
]


def _org_id(user: User, requested: UUID | None) -> UUID:
    try:
        return job_service.resolve_organization_id(user, requested)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


def _assert_job_access(user: User, job) -> None:
    if user.role == UserRole.super_admin:
        return
    if user.organization_id != job.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another organization",
        )


@router.get(
    "",
    response_model=list[JobListItem],
    summary="List job descriptions for an organization",
)
def list_jobs(
    db: DbSession,
    current_user: JobActor,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    organization_id: UUID | None = Query(default=None),
) -> list[JobListItem]:
    org_id = _org_id(current_user, organization_id)
    jobs = job_service.list_jobs(
        db,
        organization_id=org_id,
        status=status_filter,
        page=page,
        limit=limit,
    )
    return [
        JobListItem(
            **JobListItem.model_validate(job).model_dump(exclude={"applicant_count"}),
            applicant_count=len(job.applications),
        )
        for job in jobs
    ]


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job from form fields",
)
def create_job(
    body: JobCreate,
    db: DbSession,
    current_user: JobActor,
) -> JobResponse:
    org_id = _org_id(current_user, body.organization_id)
    try:
        job = job_service.create_job(
            db,
            organization_id=org_id,
            created_by=current_user.id,
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_502_BAD_GATEWAY
            if "unavailable" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=detail) from exc
    return JobResponse.model_validate(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="View job description details",
)
def get_job(
    job_id: UUID,
    db: DbSession,
    current_user: JobActor,
) -> JobResponse:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)
    return JobResponse.model_validate(job)


@router.put(
    "/{job_id}",
    response_model=JobUpdateResponse,
    summary="Update job form fields and/or status",
)
def update_job(
    job_id: UUID,
    body: JobUpdate,
    db: DbSession,
    current_user: JobActor,
) -> JobUpdateResponse:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)
    try:
        job = job_service.update_job(db, job, body)
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_502_BAD_GATEWAY
            if "unavailable" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=detail) from exc
    return JobUpdateResponse.model_validate(job)
