import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

DEFAULT_ORG_SETTINGS: dict[str, Any] = {
    "fit_labels": [
        {"id": "strong", "name": "Strong", "min_score": 8.0, "max_score": 10.0},
        {"id": "moderate", "name": "Moderate", "min_score": 6.0, "max_score": 7.9},
        {"id": "weak", "name": "Weak", "min_score": 0.0, "max_score": 5.9},
    ],
}


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organizations_is_active", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: dict(DEFAULT_ORG_SETTINGS),
        server_default=text(
            "'{\"fit_labels\": ["
            "{\"id\": \"strong\", \"name\": \"Strong\", \"min_score\": 8, \"max_score\": 10}, "
            "{\"id\": \"moderate\", \"name\": \"Moderate\", \"min_score\": 6, \"max_score\": 7.9}, "
            "{\"id\": \"weak\", \"name\": \"Weak\", \"min_score\": 0, \"max_score\": 5.9}"
            "]}'::jsonb"
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
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

    users = relationship("User", back_populates="organization")
    job_descriptions = relationship("JobDescription", back_populates="organization")
