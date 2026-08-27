"""Append-only application timeline events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.application_timeline_event import ApplicationTimelineEvent
from src.models.enums import ApplicationStatus, TimelineActorType, TimelineEventType

__all__ = [
    "append_timeline_event",
    "list_timeline_events",
    "timeline_event_types",
    "assert_not_terminal",
    "assert_job_fit_ready",
]


def append_timeline_event(
    db: Session,
    *,
    application: Application,
    event_type: TimelineEventType,
    actor_id: UUID | None = None,
    actor_type: TimelineActorType = TimelineActorType.system,
    from_status: ApplicationStatus | None = None,
    to_status: ApplicationStatus | None = None,
    metadata: dict[str, Any] | None = None,
) -> ApplicationTimelineEvent:
    event = ApplicationTimelineEvent(
        application_id=application.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status if to_status is not None else application.status,
        actor_id=actor_id,
        actor_type=actor_type,
        event_metadata=metadata,
    )
    db.add(event)
    db.flush()
    return event


def list_timeline_events(
    db: Session,
    *,
    application_id: UUID,
) -> list[ApplicationTimelineEvent]:
    stmt = (
        select(ApplicationTimelineEvent)
        .where(ApplicationTimelineEvent.application_id == application_id)
        .order_by(
            ApplicationTimelineEvent.created_at.asc(),
            ApplicationTimelineEvent.id.asc(),
        )
    )
    return list(db.scalars(stmt).all())


def timeline_event_types(db: Session, application_id: UUID) -> set[str]:
    return {
        event.event_type.value
        for event in list_timeline_events(db, application_id=application_id)
    }


def assert_not_terminal(application: Application, types: set[str]) -> None:
    if application.status == ApplicationStatus.rejected or "rejected" in types:
        raise ValueError("Application is already rejected")
    if (
        application.status == ApplicationStatus.shortlist_for_l1
        or "shortlisted_for_l1" in types
    ):
        raise ValueError("Application is already shortlisted")


def assert_job_fit_ready(
    application: Application,
    types: set[str],
    *,
    message: str = "Job fit must complete before this action",
) -> None:
    if "job_fit" not in types and application.job_fit_analysis is None:
        raise ValueError(message)
