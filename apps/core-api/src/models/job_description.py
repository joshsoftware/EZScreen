import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import JobStatus, JobType, WorkType


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        Index("ix_job_descriptions_organization_id", "organization_id"),
        Index("ix_job_descriptions_status", "status"),
        Index("ix_job_descriptions_parsed_jd", "parsed_jd", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_type: Mapped[JobType | None] = mapped_column(
        Enum(JobType, name="job_type", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    work_type: Mapped[WorkType | None] = mapped_column(
        Enum(WorkType, name="work_type", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skills: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=JobStatus.draft,
        server_default=JobStatus.draft.value,
    )
    parsed_jd: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
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

    organization = relationship("Organization", back_populates="job_descriptions")
    created_by_user = relationship(
        "User",
        back_populates="created_jobs",
        foreign_keys=[created_by],
    )
    applications = relationship(
        "Application",
        back_populates="job_description",
        cascade="all, delete-orphan",
    )
