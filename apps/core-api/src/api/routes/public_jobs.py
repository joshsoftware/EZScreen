"""Public candidate job browsing endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from src.api.deps import DbSession
from src.models.enums import JobType, WorkType
from src.schemas.public_job import PublicJobListItem, PublicJobResponse
from src.services import public_job_service

router = APIRouter(prefix="/public/jobs", tags=["Public Candidate Portal"])


@router.get(
    "",
    response_model=list[PublicJobListItem],
    summary="Candidate browse published jobs for organization subdomain",
)
def list_public_jobs(
    request: Request,
    db: DbSession,
    org_subdomain: str | None = Query(default=None),
    search: str | None = Query(default=None),
    job_type: JobType | None = Query(default=None),
    work_type: WorkType | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
) -> list[PublicJobListItem]:
    subdomain = org_subdomain or public_job_service.extract_subdomain_from_host(
        request.headers.get("host")
    )
    return public_job_service.list_public_jobs(
        db,
        org_subdomain=subdomain,
        search=search,
        job_type=job_type,
        work_type=work_type,
        page=page,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=PublicJobResponse,
    summary="Candidate view published job details",
)
def get_public_job(
    id: UUID,
    request: Request,
    db: DbSession,
    org_subdomain: str | None = Query(default=None),
) -> PublicJobResponse:
    subdomain = org_subdomain or public_job_service.extract_subdomain_from_host(
        request.headers.get("host")
    )
    job = public_job_service.get_public_job(
        db,
        job_id=id,
        org_subdomain=subdomain,
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or no longer active",
        )
    return job
