"""Bulk resume upload routes under a job."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import DbSession, require_roles
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.application import (
    ApplicationDetailResponse,
    ApplicantListItem,
    BulkCreateRequest,
    BulkCreateResponse,
    JobFitRunResponse,
    UploadUrlsRequest,
    UploadUrlsResponse,
)
from src.services import application_service, job_service

router = APIRouter(
    prefix="/jobs/{job_id}/applications",
    tags=["Candidate Applications"],
)
applicant_router = APIRouter(
    prefix="/jobs/{job_id}/applicants",
    tags=["Candidate Applications"],
)
detail_router = APIRouter(
    prefix="/applications",
    tags=["Candidate Applications"],
)

JobActor = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.hr, UserRole.organization_admin, UserRole.super_admin
        )
    ),
]


def _assert_job_access(user: User, job) -> None:
    if user.role == UserRole.super_admin:
        return
    if user.organization_id != job.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another organization",
        )


@router.post(
    "/upload-urls",
    response_model=UploadUrlsResponse,
    summary="Issue pre-signed S3 PUT URLs for HR bulk resume upload",
)
def create_upload_urls(
    job_id: UUID,
    body: UploadUrlsRequest,
    db: DbSession,
    current_user: JobActor,
) -> UploadUrlsResponse:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)
    try:
        application_service.assert_job_accepts_applications(job)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    try:
        return application_service.create_upload_urls(job, body.files)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create upload URLs: {exc}",
        ) from exc


@router.post(
    "/bulk",
    response_model=BulkCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register S3-uploaded resumes and process each independently",
)
def bulk_create_applications(
    job_id: UUID,
    body: BulkCreateRequest,
    db: DbSession,
    current_user: JobActor,
) -> BulkCreateResponse:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)
    try:
        return application_service.enqueue_bulk_resumes(job, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@applicant_router.get(
    "",
    response_model=list[ApplicantListItem],
    summary="List applicants for a job sorted by score",
)
def list_applicants(
    job_id: UUID,
    db: DbSession,
    current_user: JobActor,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=50),
) -> list[ApplicantListItem]:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)
    return application_service.list_applicants(db, job_id=job_id, page=page, limit=limit)


@router.post(
    "/{application_id}/rerun-fit",
    response_model=JobFitRunResponse,
    summary="Recalculate job-fit for an application",
)
def rerun_job_fit(
    job_id: UUID,
    application_id: UUID,
    db: DbSession,
    current_user: JobActor,
) -> JobFitRunResponse:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)

    application = application_service.get_application(db, application_id)
    if application is None or application.job_description_id != job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    try:
        return application_service.rerun_job_fit(db, application=application)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@detail_router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
    summary="View application details with parsed resume and match data",
)
def get_application(
    application_id: UUID,
    db: DbSession,
    current_user: JobActor,
) -> ApplicationDetailResponse:
    application = application_service.get_application(db, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    job = application.job_description
    if job is None:
        job = job_service.get_job(db, application.job_description_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(current_user, job)
    return application_service.application_to_detail_response(application)
