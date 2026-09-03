"""Interview session request/response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

_EMAIL_SPLIT = re.compile(r"[\s,;]+")


def _normalize_email_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip().lower() for p in _EMAIL_SPLIT.split(value) if p.strip()]
        return list(dict.fromkeys(parts))
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip().lower())
        return list(dict.fromkeys(parts))
    raise TypeError("additional_emails must be a string or list of emails")


class ScheduleInterviewSessionRequest(BaseModel):
    application_id: UUID
    interview_type: str = "screening_ai"
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, description="30, 45, or 60")
    comment: str | None = Field(default=None, max_length=500)
    time_zone: str | None = Field(default=None, max_length=64)
    gmeet_link: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional Meet link pasted by HR. If blank, a link is generated.",
    )
    additional_emails: list[EmailStr] = Field(
        default_factory=list,
        max_length=20,
        description="Extra attendees to include on the invite",
    )

    @field_validator("comment", "time_zone", "gmeet_link", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @field_validator("gmeet_link")
    @classmethod
    def validate_gmeet_link(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.lower().startswith("https://"):
            raise ValueError("gmeet_link must be an https URL")
        return value

    @field_validator("additional_emails", mode="before")
    @classmethod
    def normalize_additional_emails(cls, value: object) -> list[str]:
        return _normalize_email_list(value)

    @field_validator("interview_type")
    @classmethod
    def validate_interview_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "screening_ai":
            raise ValueError("interview_type must be screening_ai")
        return normalized

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        if value not in {30, 45, 60}:
            raise ValueError("duration_minutes must be 30, 45, or 60")
        return value

    @model_validator(mode="after")
    def require_timezone_aware(self) -> ScheduleInterviewSessionRequest:
        if self.scheduled_at.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return self


class RescheduleInterviewSessionRequest(BaseModel):
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, description="30, 45, or 60")
    comment: str | None = Field(default=None, max_length=500)
    time_zone: str | None = Field(default=None, max_length=64)
    additional_emails: list[EmailStr] = Field(
        default_factory=list,
        max_length=20,
        description="Extra attendees to include on the invite",
    )

    @field_validator("comment", "time_zone", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @field_validator("additional_emails", mode="before")
    @classmethod
    def normalize_additional_emails(cls, value: object) -> list[str]:
        return _normalize_email_list(value)

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        if value not in {30, 45, 60}:
            raise ValueError("duration_minutes must be 30, 45, or 60")
        return value

    @model_validator(mode="after")
    def require_timezone_aware(self) -> RescheduleInterviewSessionRequest:
        if self.scheduled_at.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return self


class InterviewSessionResponse(BaseModel):
    id: UUID
    application_id: UUID
    scheduled_by: UUID
    interview_type: str
    status: str
    scheduled_at: datetime | None = None
    comment: str | None = None
    interview_metadata: dict | None = None
    gmeet_link: str | None = None
    bot_id: str | None = None
    bot_status: str | None = None
    additional_emails: list[str] = Field(default_factory=list)
    generated_questions: list | dict | None = None
    created_at: datetime
