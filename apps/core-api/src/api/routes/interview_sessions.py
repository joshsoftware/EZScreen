"""Interview session routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import DbSession, require_roles, verify_internal_service
from src.models.enums import UserRole
from src.models.interview_session import InterviewSession
from src.models.user import User
from src.schemas.interview_analysis import (
    SaveEvaluationRequest,
    SaveEvaluationSummaryRequest,
    SaveQaTranscriptRequest,
    SaveTranscriptRequest,
    SuccessMessageResponse,
)
from src.schemas.interview_session import (
    InterviewSessionResponse,
    RescheduleInterviewSessionRequest,
    ScheduleInterviewSessionRequest,
)
from src.services import (
    application_service,
    interview_analysis_service,
    job_service,
    interview_session_service,
)

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


InternalService = Annotated[None, Depends(verify_internal_service)]


def _get_session_or_404(db: DbSession, session_id: UUID) -> InterviewSession:
    session = interview_session_service.get_interview_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )
    return session


def _assert_job_access(user: User, job) -> None:
    if user.role == UserRole.super_admin:
        return
    if user.organization_id != job.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another organization",
        )


def _get_session_for_org(
    db: DbSession,
    session_id: UUID,
    current_user: User,
) -> InterviewSession:
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
    return session


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


@router.post(
    "/{session_id}/reschedule",
    response_model=InterviewSessionResponse,
    summary="Reschedule an active AI screening session",
)
def reschedule_interview_session(
    session_id: UUID,
    body: RescheduleInterviewSessionRequest,
    db: DbSession,
    current_user: JobActor,
) -> InterviewSessionResponse:
    session = _get_session_for_org(db, session_id, current_user)
    try:
        updated = interview_session_service.reschedule_interview_session(
            db,
            session=session,
            actor_id=current_user.id,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return interview_session_service.interview_session_to_response(updated)


@router.post(
    "/{session_id}/qa-transcript",
    response_model=SuccessMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save technical Q&A transcript for a screening question",
)
def save_qa_transcript(
    session_id: UUID,
    body: SaveQaTranscriptRequest,
    db: DbSession,
    _internal: InternalService,
) -> SuccessMessageResponse:
    session = _get_session_or_404(db, session_id)
    interview_analysis_service.save_qa_transcript(db, session, body)
    return SuccessMessageResponse(message="Transcript saved successfully.")


@router.post(
    "/{session_id}/evaluation",
    response_model=SuccessMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append per-question screening evaluation",
)
def save_evaluation(
    session_id: UUID,
    body: SaveEvaluationRequest,
    db: DbSession,
    _internal: InternalService,
) -> SuccessMessageResponse:
    session = _get_session_or_404(db, session_id)
    interview_analysis_service.save_evaluation(db, session, body)
    return SuccessMessageResponse(message="Evaluation appended successfully.")


@router.post(
    "/{session_id}/evaluation/summary",
    response_model=SuccessMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save final screening interview summary",
)
def save_evaluation_summary(
    session_id: UUID,
    body: SaveEvaluationSummaryRequest,
    db: DbSession,
    _internal: InternalService,
) -> SuccessMessageResponse:
    session = _get_session_or_404(db, session_id)
    interview_analysis_service.save_evaluation_summary(db, session, body)
    return SuccessMessageResponse(message="Summary saved successfully.")


@router.post(
    "/{session_id}/transcript",
    response_model=SuccessMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save raw conversational transcript metadata",
)
def save_conversation_transcript(
    session_id: UUID,
    body: SaveTranscriptRequest,
    db: DbSession,
    _internal: InternalService,
) -> SuccessMessageResponse:
    session = _get_session_or_404(db, session_id)
    interview_analysis_service.save_conversation_transcript(db, session, body)
    return SuccessMessageResponse(message="Metadata saved successfully.")


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
    session = _get_session_for_org(db, session_id, current_user)
    return interview_session_service.interview_session_to_response(session)
