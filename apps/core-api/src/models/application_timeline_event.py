import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.application import APPLICATION_STATUS_ENUM
from src.models.enums import ApplicationStatus, TimelineActorType, TimelineEventType


class ApplicationTimelineEvent(Base):
    """Append-only application timeline (status stays applied until screening)."""

    __tablename__ = "application_timeline_events"
    __table_args__ = (
        Index(
            "ix_application_timeline_events_application_created",
            "application_id",
            "created_at",
        ),
        Index("ix_application_timeline_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(
            TimelineEventType,
            name="timeline_event_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        APPLICATION_STATUS_ENUM,
        nullable=True,
    )
    to_status: Mapped[ApplicationStatus | None] = mapped_column(
        APPLICATION_STATUS_ENUM,
        nullable=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[TimelineActorType] = mapped_column(
        Enum(
            TimelineActorType,
            name="timeline_actor_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TimelineActorType.system,
        server_default=TimelineActorType.system.value,
    )
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    application = relationship("Application", back_populates="timeline_events")
    actor = relationship("User")
