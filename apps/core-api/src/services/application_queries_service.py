"""Application read/query helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from src.models.application import Application
from src.models.enums import InterviewStatus
from src.models.interview_analysis import InterviewAnalysis
from src.models.interview_session import InterviewSession
from src.schemas.application import (
    ApplicationDetailResponse,
    ApplicationResumeResponse,
    ApplicantListItem,
    TimelineEventResponse,
)
from src.services import storage_service
from src.services.application_timeline_service import list_timeline_events

__all__ = [
    "list_applicants",
    "get_application",
    "application_to_detail_response",
    "application_timeline_response",
    "application_resume_response",
    "application_resume_file",
]


def list_applicants(
    db: Session,
    *,
    job_id: UUID,
    page: int = 1,
    limit: int = 50,
) -> list[ApplicantListItem]:
    offset = max(page - 1, 0) * limit
    stmt = (
        select(Application)
        .options(selectinload(Application.candidate))
        .where(Application.job_description_id == job_id)
        .order_by(Application.resume_score.desc().nullslast(), Application.created_at.desc())
        .offset(offset)
        .limit(min(limit, 50))
    )
    applications = list(db.scalars(stmt).all())
    application_ids = [application.id for application in applications]
    latest_screenings = _latest_screenings(db, application_ids)
    interview_scores = _latest_interview_scores(db, application_ids)
    # A missed interview has no score: "—", not a red 0.0 (Bug-47).
    for application_id, screening in latest_screenings.items():
        if screening.status == InterviewStatus.no_show:
            interview_scores[application_id] = None
    items = []
    for application in applications:
        screening = latest_screenings.get(application.id)
        items.append(
            ApplicantListItem(
                id=application.id,
                job_description_id=application.job_description_id,
                candidate_id=application.candidate_id,
                status=application.status.value,
                source=application.source.value,
                candidate_yoe=application.candidate_yoe,
                resume_score=application.resume_score,
                interview_score=interview_scores.get(application.id),
                screening_status=screening.status.value if screening else None,
                interview_scheduled_at=screening.scheduled_at if screening else None,
                first_name=application.candidate.first_name if application.candidate else None,
                last_name=application.candidate.last_name if application.candidate else None,
                email=application.candidate.email if application.candidate else None,
                phone=application.candidate.phone if application.candidate else None,
                created_at=application.created_at,
                updated_at=application.updated_at,
            )
        )
    return items


def _latest_screenings(db: Session, application_ids: list[UUID]) -> dict[UUID, InterviewSession]:
    """Each application's newest screening session, after marking screenings
    whose time passed with nobody attending as no-show."""
    if not application_ids:
        return {}
    from src.services.interview_session_service import mark_missed_screenings

    sessions = list(
        db.scalars(
            select(InterviewSession)
            .where(InterviewSession.application_id.in_(application_ids))
            .order_by(InterviewSession.created_at.desc())
        ).all()
    )
    mark_missed_screenings(db, sessions)
    latest: dict[UUID, InterviewSession] = {}
    for session in sessions:
        latest.setdefault(session.application_id, session)
    return latest


def _latest_interview_scores(db: Session, application_ids: list[UUID]) -> dict[UUID, float | None]:
    """Overall screening score from each application's newest interview analysis."""
    if not application_ids:
        return {}
    score_text = InterviewAnalysis.analysis_result["final_summary"]["overall_score"].astext
    # No scored answers (no-show, silent candidate, a new booking after one)
    # means no interview score: "—", not 0.0 (Bug-47).
    answered = func.jsonb_array_length(
        func.coalesce(InterviewAnalysis.analysis_result["evaluations"], text("'[]'::jsonb"))
    )
    stmt = (
        select(InterviewAnalysis.application_id, score_text, answered)
        .where(InterviewAnalysis.application_id.in_(application_ids))
        .distinct(InterviewAnalysis.application_id)
        .order_by(InterviewAnalysis.application_id, InterviewAnalysis.created_at.desc())
    )
    scores: dict[UUID, float | None] = {}
    for application_id, raw_score, answered_count in db.execute(stmt):
        if not answered_count or raw_score is None or raw_score == "":
            scores[application_id] = None
            continue
        try:
            scores[application_id] = float(raw_score)
        except (TypeError, ValueError):
            scores[application_id] = None
    return scores


def get_application(db: Session, application_id: UUID) -> Application | None:
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job_description),
        )
        .where(Application.id == application_id)
    )
    return db.scalar(stmt)


def application_to_detail_response(
    application: Application,
) -> ApplicationDetailResponse:
    candidate = application.candidate
    resume_key = (application.resume_url or "").strip() or None
    return ApplicationDetailResponse(
        id=application.id,
        job_description_id=application.job_description_id,
        candidate_id=application.candidate_id,
        status=application.status.value,
        source=application.source.value,
        candidate_yoe=application.candidate_yoe,
        resume_score=application.resume_score,
        first_name=candidate.first_name if candidate else None,
        last_name=candidate.last_name if candidate else None,
        email=candidate.email if candidate else None,
        phone=candidate.phone if candidate else None,
        has_resume=bool(resume_key),
        resume_file_name=(
            storage_service.resume_display_name(resume_key) if resume_key else None
        ),
        parsed_resume=application.parsed_resume,
        job_fit_analysis=application.job_fit_analysis,
    )


def application_resume_response(application: Application) -> ApplicationResumeResponse:
    resume_key = (application.resume_url or "").strip()
    if not resume_key:
        raise LookupError("Resume file is not available for this application")

    file_name = storage_service.resume_display_name(resume_key)
    content_type = storage_service.guess_resume_content_type(resume_key)
    preview_url, expires_at = storage_service.create_presigned_download_url(
        resume_key,
        disposition="inline",
        file_name=file_name,
        content_type=content_type,
    )
    download_url, _ = storage_service.create_presigned_download_url(
        resume_key,
        disposition="attachment",
        file_name=file_name,
        content_type=content_type,
    )
    return ApplicationResumeResponse(
        application_id=application.id,
        file_name=file_name,
        content_type=content_type,
        preview_url=preview_url,
        download_url=download_url,
        expires_at=expires_at,
        previewable=content_type == "application/pdf",
    )


def application_resume_file(application: Application) -> storage_service.ResumeObjectPayload:
    resume_key = (application.resume_url or "").strip()
    if not resume_key:
        raise LookupError("Resume file is not available for this application")
    return storage_service.get_resume_object(resume_key)


def application_timeline_response(
    db: Session,
    *,
    application_id: UUID,
) -> list[TimelineEventResponse]:
    events = list_timeline_events(db, application_id=application_id)
    return [
        TimelineEventResponse(
            id=event.id,
            application_id=event.application_id,
            event_type=event.event_type.value,
            from_status=event.from_status.value if event.from_status else None,
            to_status=event.to_status.value if event.to_status else None,
            actor_id=event.actor_id,
            actor_type=event.actor_type.value,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
        for event in events
    ]
