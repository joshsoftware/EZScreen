import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import InterviewStatus, InterviewType


class InterviewSession(Base):
    __tablename__ = "interview_session"
    __table_args__ = (
        Index("ix_interview_session_application_id", "application_id"),
        Index("ix_interview_session_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    scheduled_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    interview_type: Mapped[InterviewType] = mapped_column(
        Enum(
            InterviewType,
            name="interview_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=InterviewType.screening_ai,
        server_default=InterviewType.screening_ai.value,
    )
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(
            InterviewStatus,
            name="interview_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=InterviewStatus.scheduled,
        server_default=InterviewStatus.scheduled.value,
    )
    interview_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_questions: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    application = relationship("Application", back_populates="interview_sessions")
    scheduled_by_user = relationship(
        "User",
        back_populates="scheduled_interviews",
        foreign_keys=[scheduled_by],
    )
    analysis = relationship(
        "InterviewAnalysis",
        back_populates="interview_session",
        uselist=False,
        cascade="all, delete-orphan",
    )
