import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import InterviewType


class InterviewAnalysis(Base):
    __tablename__ = "interview_analysis"
    __table_args__ = (
        Index("ix_interview_analysis_application_id", "application_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    interview_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_session.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    question_answer: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    interview_type: Mapped[InterviewType | None] = mapped_column(
        Enum(
            InterviewType,
            name="interview_type",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    interview_session = relationship(
        "InterviewSession",
        back_populates="analysis",
    )
    application = relationship("Application", back_populates="interview_analyses")
