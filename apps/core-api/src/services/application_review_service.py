"""HR review and reject transitions for applications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.enums import (
    ApplicationStatus,
    TimelineActorType,
    TimelineEventType,
)
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


def reject_application(
    db: Session,
    *,
    application: Application,
    actor_id: UUID,
    reason: str | None = None,
) -> Application:
    types = timeline_event_types(db, application.id)
    assert_not_terminal(application, types)

    # This slice: reject after fit / during HR review (pre-screening).
    if application.status not in _PRE_SCREENING_STATUSES:
        raise ValueError("Application cannot be rejected in its current status")

    assert_job_fit_ready(
        application,
        types,
        message="Job fit must complete before rejecting",
    )

    from_status = application.status
    application.status = ApplicationStatus.rejected
    metadata = {"reason": reason.strip()} if reason and reason.strip() else None
    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.rejected,
        actor_id=actor_id,
        actor_type=TimelineActorType.user,
        from_status=from_status,
        to_status=ApplicationStatus.rejected,
        metadata=metadata,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
