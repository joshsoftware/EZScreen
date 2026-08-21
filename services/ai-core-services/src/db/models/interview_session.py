import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, DateTime, Index, text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.db.base import Base


class DBInterviewSession(Base):
    __tablename__ = "interview_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        info={"description": "Unique identifier for the interview session"},
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        info={"description": "Foreign key reference to candidate application"},
    )

    scheduled_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        info={"description": "Foreign key reference to HR user who scheduled the session"},
    )

    interview_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="screening_ai",
        info={"description": "Type of interview session (screening_ai)"},
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="scheduled",
        info={"description": "Current state of interview session (scheduled, in_progress, completed, failed)"},
    )

    interview_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        info={"description": "Session operational metadata payload"},
    )

    comment: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        info={"description": "HR notes or operational comments"},
    )

    generated_questions: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        info={"description": "Pre-generated question set for the screening interview"},
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        info={"description": "Scheduled time slot for the interview"},
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        info={"description": "Timestamp when interview call concluded"},
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        info={"description": "Timestamp when the record was created"},
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
        info={"description": "Timestamp when the record was last updated"},
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        info={"description": "Timestamp when the record was soft-deleted"},
    )

    __table_args__ = (
        Index("idx_interview_session_app_id", "application_id"),
        Index("idx_interview_session_status", "status"),
    )

    def to_response(self) -> Any:
        from src.meeting_bot.schemas import InterviewSessionDetailResponse
        return InterviewSessionDetailResponse(
            id=str(self.id),
            application_id=str(self.application_id),
            scheduled_by=str(self.scheduled_by) if self.scheduled_by else None,
            interview_type=self.interview_type,
            status=self.status,
            scheduled_at=self.scheduled_at.isoformat() if self.scheduled_at else None,
            generated_questions=self.generated_questions,
            interview_metadata=self.interview_metadata,
            created_at=self.created_at.isoformat() if self.created_at else None,
            updated_at=self.updated_at.isoformat() if self.updated_at else None,
        )
