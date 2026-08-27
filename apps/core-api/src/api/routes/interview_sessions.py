"""Interview session routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import DbSession, require_roles
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.interview_session import (
    InterviewSessionResponse,
    ScheduleInterviewSessionRequest,
)
from src.services import application_service, job_service, interview_session_service

router = APIRouter(
    prefix="/interview-sessions",
    tags=["Interview Sessions & Analysis"],
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
    "",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule AI screening interview session",
)
def schedule_interview_session(
    body: ScheduleInterviewSessionRequest,
    db: DbSession,
    current_user: JobActor,
) -> InterviewSessionResponse:
    application = application_service.get_application(db, body.application_id)
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
        session = interview_session_service.schedule_interview_session(
            db,
            application=application,
            actor_id=current_user.id,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return interview_session_service.interview_session_to_response(session)


@router.get(
    "/{session_id}",
    response_model=InterviewSessionResponse,
    summary="View interview session details",
)
def get_interview_session(
    session_id: UUID,
    db: DbSession,
    current_user: JobActor,
) -> InterviewSessionResponse:
    session = interview_session_service.get_interview_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )

    application = session.application
    if application is None:
        application = application_service.get_application(db, session.application_id)
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

    return interview_session_service.interview_session_to_response(session)
