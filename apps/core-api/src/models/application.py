import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import ApplicationStatus


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint(
            "job_description_id",
            "candidate_id",
            name="uq_applications_job_candidate",
        ),
        Index("ix_applications_job_description_id", "job_description_id"),
        Index("ix_applications_resume_score", "resume_score"),
        Index("ix_applications_status", "status"),
        Index(
            "ix_applications_job_status_score",
            "job_description_id",
            "status",
            "resume_score",
        ),
        Index("ix_applications_candidate_yoe", "candidate_yoe"),
        Index("ix_applications_parsed_resume", "parsed_resume", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_description_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_descriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    resume_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    parsed_resume: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    candidate_yoe: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    job_fit_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ApplicationStatus.applied,
        server_default=ApplicationStatus.applied.value,
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.utcnow,
    )

    job_description = relationship("JobDescription", back_populates="applications")
    candidate = relationship(
        "User",
        back_populates="applications",
        foreign_keys=[candidate_id],
    )
    interview_sessions = relationship(
        "InterviewSession",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    interview_analyses = relationship(
        "InterviewAnalysis",
        back_populates="application",
        cascade="all, delete-orphan",
    )
