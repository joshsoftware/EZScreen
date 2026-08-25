import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, DateTime, Text, Index, text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.db.base import Base


class DBInterviewAnalysis(Base):
    __tablename__ = "interview_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        info={"description": "Unique identifier for the interview analysis report"},
    )

    interview_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        info={"description": "Unique foreign key reference to interview session (1-to-1)"},
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        info={"description": "Foreign key reference to candidate application"},
    )

    analysis_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        info={"description": "AI screening evaluation feedback, recommendations, and scores"},
    )

    question_answer: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        info={"description": "Structured Q&A transcript analysis and answer depth scores"},
    )

    recording_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        info={"description": "Storage URL for call recording audio/video"},
    )

    interview_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="screening_ai",
        info={"description": "Type of interview session (screening_ai)"},
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
        Index("idx_interview_analysis_session_id", "interview_session_id"),
        Index("idx_interview_analysis_app_id", "application_id"),
    )

    def to_response(self) -> Any:
        from src.meeting_bot.schemas import InterviewAnalysisDetailResponse
        return InterviewAnalysisDetailResponse(
            id=str(self.id),
            interview_session_id=str(self.interview_session_id),
            application_id=str(self.application_id),
            analysis_result=self.analysis_result,
            question_answer=self.question_answer,
            recording_url=self.recording_url,
            interview_type=self.interview_type,
            created_at=self.created_at.isoformat() if self.created_at else None,
            updated_at=self.updated_at.isoformat() if self.updated_at else None,
        )
