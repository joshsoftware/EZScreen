"""Bulk resume upload routes under a job."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from src.api.deps import DbSession, require_roles
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.application import (
    ApplicationDetailResponse,
    ApplicationRejectRequest,
    ApplicationResumeResponse,
    ApplicantListItem,
    BulkCreateRequest,
    BulkCreateResponse,
    JobFitRunResponse,
    TimelineEventResponse,
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
        return application_service.enqueue_bulk_resumes(
            job, body, actor_id=current_user.id
        )
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


@detail_router.post(
    "/{application_id}/hr-review",
    response_model=ApplicationDetailResponse,
    summary="Move application into HR review (timeline only; status stays applied)",
)
def move_application_to_hr_review(
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
    try:
        updated = application_service.move_to_hr_review(
            db, application=application, actor_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return application_service.application_to_detail_response(updated)


@detail_router.post(
    "/{application_id}/reject",
    response_model=ApplicationDetailResponse,
    summary="Reject application after fit / during HR review",
)
def reject_application(
    application_id: UUID,
    db: DbSession,
    current_user: JobActor,
    body: ApplicationRejectRequest = ApplicationRejectRequest(),
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
    try:
        updated = application_service.reject_application(
            db,
            application=application,
            actor_id=current_user.id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return application_service.application_to_detail_response(updated)


@detail_router.get(
    "/{application_id}/resume",
    response_model=ApplicationResumeResponse,
    summary="Issue pre-signed URLs to preview or download the candidate resume",
)
def get_application_resume(
    application_id: UUID,
    db: DbSession,
    current_user: JobActor,
) -> ApplicationResumeResponse:
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
    try:
        return application_service.application_resume_response(application)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create resume URLs: {exc}",
        ) from exc


@detail_router.get(
    "/{application_id}/resume/file",
    summary="Stream resume file through the API (preview or download)",
    responses={200: {"content": {"application/pdf": {}}}},
)
def stream_application_resume(
    application_id: UUID,
    db: DbSession,
    current_user: JobActor,
    disposition: str = Query("inline", pattern="^(inline|attachment)$"),
) -> StreamingResponse:
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
    try:
        payload = application_service.application_resume_file(application)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to load resume file: {exc}",
        ) from exc

    file_name = payload["file_name"]
    headers = {
        "Content-Disposition": f'{disposition}; filename="{file_name}"',
        "Cache-Control": "private, no-store",
    }
    if payload.get("content_length") is not None:
        headers["Content-Length"] = str(payload["content_length"])

    return StreamingResponse(
        payload["body"].iter_chunks(),
        media_type=payload["content_type"],
        headers=headers,
    )


@detail_router.get(
    "/{application_id}/timeline",
    response_model=list[TimelineEventResponse],
    summary="List application timeline events in chronological order",
)
def get_application_timeline(
    application_id: UUID,
    db: DbSession,
    current_user: JobActor,
) -> list[TimelineEventResponse]:
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
    return application_service.application_timeline_response(
        db, application_id=application.id
    )
