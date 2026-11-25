"""HR review and reject transitions for applications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.enums import (
    ApplicationStatus,
    InterviewStatus,
    TimelineActorType,
    TimelineEventType,
)
from src.models.interview_session import InterviewSession
from src.services.application_timeline_service import (
    append_timeline_event,
    assert_job_fit_ready,
    assert_not_terminal,
    timeline_event_types,
)

__all__ = [
    "move_to_hr_review",
    "reject_application",
]


_PRE_SCREENING_STATUSES = frozenset({ApplicationStatus.applied})


def move_to_hr_review(
    db: Session,
    *,
    application: Application,
    actor_id: UUID,
) -> Application:
    types = timeline_event_types(db, application.id)
    assert_not_terminal(application, types)

    if application.status not in _PRE_SCREENING_STATUSES:
        raise ValueError("Only pre-screening applications can move to HR review")

    if "under_hr_review" in types:
        raise ValueError("Application is already under HR review")

    assert_job_fit_ready(
        application,
        types,
        message="Job fit must complete before HR review",
    )

    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.under_hr_review,
        actor_id=actor_id,
        actor_type=TimelineActorType.user,
        from_status=application.status,
        to_status=application.status,
    )
    db.commit()
    db.refresh(application)
    return application


# The screening is over (attended or not), so HR can decide on the candidate.
_FINISHED_SCREENING_STATUSES = frozenset(
    {
        InterviewStatus.completed,
        InterviewStatus.no_show,
        InterviewStatus.failed,
        InterviewStatus.cancelled,
    }
)


def _latest_screening_status(db: Session, application_id: UUID) -> InterviewStatus | None:
    stmt = (
        select(InterviewSession.status)
        .where(InterviewSession.application_id == application_id)
        .order_by(InterviewSession.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _rejection_status(db: Session, application: Application) -> ApplicationStatus:
    """Which rejection applies, from where the application is in screening.

    Before any screening the decision rests on the job analysis score; after
    the screening has finished it rests on the interview.
    """
    if application.status in _PRE_SCREENING_STATUSES:
        return ApplicationStatus.rejected_low_score
    if application.status == ApplicationStatus.interview_completed:
        return ApplicationStatus.rejected_screening
    if (
        application.status == ApplicationStatus.interview_scheduled
        and _latest_screening_status(db, application.id) in _FINISHED_SCREENING_STATUSES
    ):
        return ApplicationStatus.rejected_screening
    raise ValueError(
        "Application cannot be rejected while its screening is still scheduled or under way"
    )


def reject_application(
    db: Session,
    *,
    application: Application,
    actor_id: UUID,
    reason: str | None = None,
) -> Application:
    types = timeline_event_types(db, application.id)
    assert_not_terminal(application, types)

    rejection_status = _rejection_status(db, application)
    if rejection_status == ApplicationStatus.rejected_low_score:
        assert_job_fit_ready(
            application,
            types,
            message="Job fit must complete before rejecting",
        )

    from_status = application.status
    application.status = rejection_status
    metadata = {"reason": reason.strip()} if reason and reason.strip() else None
    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.rejected,
        actor_id=actor_id,
        actor_type=TimelineActorType.user,
        from_status=from_status,
        to_status=rejection_status,
        metadata=metadata,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
