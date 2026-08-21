import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import UserRole, UserStatus


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_role", "role"),
        Index("ix_users_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=UserStatus.active,
        server_default=UserStatus.active.value,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
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

    organization = relationship("Organization", back_populates="users")
    created_jobs = relationship(
        "JobDescription",
        back_populates="created_by_user",
        foreign_keys="JobDescription.created_by",
    )
    applications = relationship(
        "Application",
        back_populates="candidate",
        foreign_keys="Application.candidate_id",
    )
    scheduled_interviews = relationship(
        "InterviewSession",
        back_populates="scheduled_by_user",
        foreign_keys="InterviewSession.scheduled_by",
    )
