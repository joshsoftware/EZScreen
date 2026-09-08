"""Public candidate job browsing endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import DbSession
from src.models.enums import JobType, WorkType
from src.schemas.public_job import (
    PublicCandidateApplyRequest,
    PublicCandidateApplyResponse,
    PublicJobListItem,
    PublicJobResponse,
)
from src.services import public_job_service

router = APIRouter(prefix="/public", tags=["Public Candidate Portal"])


@router.get(
    "/{org_name}/jobs",
    response_model=list[PublicJobListItem],
    summary="Candidate browse published jobs for organization name",
)
def list_public_jobs_by_org_name(
    org_name: str,
    db: DbSession,
    search: str | None = Query(default=None),
    job_type: JobType | None = Query(default=None),
    work_type: WorkType | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
) -> list[PublicJobListItem]:
    return public_job_service.list_public_jobs(
        db,
        org_name=org_name,
        search=search,
        job_type=job_type,
        work_type=work_type,
        page=page,
        limit=limit,
    )


@router.get(
    "/{org_name}/jobs/{id}",
    response_model=PublicJobResponse,
    summary="Candidate view published job details for organization name",
)
def get_public_job_by_org_name(
    org_name: str,
    id: UUID,
    db: DbSession,
) -> PublicJobResponse:
    job = public_job_service.get_public_job(
        db,
        job_id=id,
        org_name=org_name,
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or no longer active",
        )
    return job


@router.post(
    "/{org_name}/jobs/{id}/apply",
    response_model=PublicCandidateApplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Candidate submit job application",
)
def apply_public_job(
    org_name: str,
    id: UUID,
    body: PublicCandidateApplyRequest,
    db: DbSession,
) -> PublicCandidateApplyResponse:
    job = public_job_service.get_public_job(db, job_id=id, org_name=org_name)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or no longer active",
        )
    try:
        return public_job_service.submit_public_application(
            db,
            job_id=id,
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        msg = str(exc)
        if "ALREADY_APPLIED" in msg or "already applied" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already applied for this position",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc
