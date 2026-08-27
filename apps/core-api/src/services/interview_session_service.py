"""Schedule AI screening interview sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models.application import Application
from src.models.enums import (
    ApplicationStatus,
    InterviewStatus,
    InterviewType,
    TimelineActorType,
    TimelineEventType,
)
from src.models.interview_session import InterviewSession
from src.schemas.interview_session import (
    InterviewSessionResponse,
    ScheduleInterviewSessionRequest,
)
from src.services.application_timeline_service import (
    append_timeline_event,
    assert_job_fit_ready,
    assert_not_terminal,
    timeline_event_types,
)
from src.services.email_service import (
    ScreeningInvitePayload,
    ScreeningInviteResult,
    send_screening_invite,
)
from src.services.meet_link_service import ScreeningMeetResult, create_screening_meet

__all__ = [
    "schedule_interview_session",
    "get_interview_session",
    "interview_session_to_response",
]

_ACTIVE_SESSION_STATUSES = frozenset(
    {
        InterviewStatus.scheduled,
        InterviewStatus.rescheduled,
    }
)


def get_interview_session(db: Session, session_id: UUID) -> InterviewSession | None:
    stmt = (
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.application).selectinload(
                Application.job_description
            )
        )
        .where(InterviewSession.id == session_id)
    )
    return db.scalar(stmt)


def interview_session_to_response(session: InterviewSession) -> InterviewSessionResponse:
    meta = session.interview_metadata if isinstance(session.interview_metadata, dict) else {}
    gmeet = meta.get("gmeet_link") if isinstance(meta.get("gmeet_link"), str) else None
    raw_extra = meta.get("additional_emails")
    if not isinstance(raw_extra, list):
        raw_extra = meta.get("attendees")
    additional = (
        [email for email in raw_extra if isinstance(email, str)]
        if isinstance(raw_extra, list)
        else []
    )
    return InterviewSessionResponse(
        id=session.id,
        application_id=session.application_id,
        scheduled_by=session.scheduled_by,
        interview_type=session.interview_type.value,
        status=session.status.value,
        scheduled_at=session.scheduled_at,
        comment=session.comment,
        interview_metadata=session.interview_metadata,
        gmeet_link=gmeet,
        additional_emails=additional,
        generated_questions=session.generated_questions,
        created_at=session.created_at,
    )


def _has_active_session(db: Session, application_id: UUID) -> bool:
    stmt = select(InterviewSession.id).where(
        InterviewSession.application_id == application_id,
        InterviewSession.status.in_(_ACTIVE_SESSION_STATUSES),
    )
    return db.scalar(stmt) is not None


def _candidate_label(application: Application) -> str:
    candidate = application.candidate
    if candidate is None:
        return "Candidate"
    parts = [
        (candidate.first_name or "").strip(),
        (candidate.last_name or "").strip(),
    ]
    name = " ".join(p for p in parts if p)
    return name or candidate.email or "Candidate"


def _attendee_emails(
    application: Application,
    additional_emails: list[str],
) -> list[str]:
    emails: list[str] = []
    candidate = application.candidate
    if candidate is not None and isinstance(candidate.email, str) and candidate.email.strip():
        emails.append(candidate.email.strip().lower())
    for email in additional_emails:
        if isinstance(email, str) and email.strip():
            emails.append(email.strip().lower())
    return list(dict.fromkeys(emails))


def _assert_schedulable(
    db: Session,
    *,
    application: Application,
    scheduled_at: datetime,
) -> set[str]:
    types = timeline_event_types(db, application.id)
    assert_not_terminal(application, types)

    if application.status != ApplicationStatus.applied:
        raise ValueError("Only applications in HR review can be scheduled")

    assert_job_fit_ready(
        application,
        types,
        message="Job fit must complete before scheduling screening",
    )

    if "under_hr_review" not in types:
        raise ValueError("Application must be under HR review before scheduling")

    if "screening_scheduled" in types or _has_active_session(db, application.id):
        raise ValueError("Screening is already scheduled for this application")

    if scheduled_at.astimezone(timezone.utc) <= datetime.now(timezone.utc):
        raise ValueError("scheduled_at must be in the future")

    return types


def _resolve_meet(
    *,
    body: ScheduleInterviewSessionRequest,
    attendees: list[str],
) -> ScreeningMeetResult:
    if body.gmeet_link:
        return {
            "gmeet_link": body.gmeet_link,
            "duration_minutes": body.duration_minutes,
            "provider": "manual",
            "meet_space_name": None,
            "meeting_code": None,
            "time_zone": body.time_zone,
            "attendees": attendees,
        }
    return create_screening_meet(
        scheduled_at=body.scheduled_at,
        duration_minutes=body.duration_minutes,
        time_zone=body.time_zone,
        attendees=attendees,
    )


def _build_session_metadata(
    *,
    meet: ScreeningMeetResult,
    body: ScheduleInterviewSessionRequest,
    attendees: list[str],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "gmeet_link": meet["gmeet_link"],
        "duration_minutes": meet["duration_minutes"],
        "provider": meet["provider"],
        "meet_space_name": meet.get("meet_space_name"),
        "meeting_code": meet.get("meeting_code"),
        "attendees": meet.get("attendees") or attendees,
        "additional_emails": [str(email) for email in body.additional_emails],
    }
    if body.time_zone:
        metadata["time_zone"] = body.time_zone
    elif meet.get("time_zone"):
        metadata["time_zone"] = meet["time_zone"]
    return metadata


def _persist_scheduled_session(
    db: Session,
    *,
    application: Application,
    actor_id: UUID,
    body: ScheduleInterviewSessionRequest,
    metadata: dict[str, Any],
) -> InterviewSession:
    session = InterviewSession(
        application_id=application.id,
        scheduled_by=actor_id,
        interview_type=InterviewType.screening_ai,
        status=InterviewStatus.scheduled,
        scheduled_at=body.scheduled_at,
        comment=body.comment,
        interview_metadata=metadata,
        generated_questions=None,
    )
    db.add(session)
    db.flush()

    from_status = application.status
    application.status = ApplicationStatus.interview_scheduled
    db.add(application)

    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.screening_scheduled,
        actor_id=actor_id,
        actor_type=TimelineActorType.user,
        from_status=from_status,
        to_status=ApplicationStatus.interview_scheduled,
        metadata={
            "interview_session_id": str(session.id),
            "scheduled_at": body.scheduled_at.isoformat(),
            "gmeet_link": metadata["gmeet_link"],
            "duration_minutes": body.duration_minutes,
            "provider": metadata["provider"],
            "attendees": metadata["attendees"],
            "additional_emails": metadata["additional_emails"],
            **(
                {"time_zone": metadata["time_zone"]}
                if metadata.get("time_zone")
                else {}
            ),
        },
    )
    return session


def _send_invite_and_timeline(
    db: Session,
    *,
    application: Application,
    session: InterviewSession,
    candidate_name: str,
    job_title: str,
    body: ScheduleInterviewSessionRequest,
    metadata: dict[str, Any],
) -> ScreeningInviteResult:
    invite = send_screening_invite(
        ScreeningInvitePayload(
            to_emails=list(metadata["attendees"]),
            candidate_name=candidate_name,
            job_title=job_title,
            scheduled_at=body.scheduled_at,
            duration_minutes=body.duration_minutes,
            gmeet_link=metadata["gmeet_link"],
            time_zone=metadata.get("time_zone"),
            comment=body.comment,
        )
    )
    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.invite_sent,
        actor_type=TimelineActorType.system,
        from_status=ApplicationStatus.interview_scheduled,
        to_status=ApplicationStatus.interview_scheduled,
        metadata={
            "interview_session_id": str(session.id),
            "gmeet_link": metadata["gmeet_link"],
            "recipients": invite.get("recipients") or [],
            "email_mode": invite.get("mode"),
            "sent": bool(invite.get("sent")),
            **({"reason": invite["reason"]} if invite.get("reason") else {}),
        },
    )
    return invite


def schedule_interview_session(
    db: Session,
    *,
    application: Application,
    actor_id: UUID,
    body: ScheduleInterviewSessionRequest,
) -> InterviewSession:
    _assert_schedulable(db, application=application, scheduled_at=body.scheduled_at)

    job = application.job_description
    job_title = job.title if job is not None else "Role"
    candidate_name = _candidate_label(application)
    attendees = _attendee_emails(application, list(body.additional_emails))

    meet = _resolve_meet(body=body, attendees=attendees)
    metadata = _build_session_metadata(meet=meet, body=body, attendees=attendees)
    session = _persist_scheduled_session(
        db,
        application=application,
        actor_id=actor_id,
        body=body,
        metadata=metadata,
    )
    _send_invite_and_timeline(
        db,
        application=application,
        session=session,
        candidate_name=candidate_name,
        job_title=job_title,
        body=body,
        metadata=metadata,
    )

    db.commit()
    db.refresh(session)
    return session
