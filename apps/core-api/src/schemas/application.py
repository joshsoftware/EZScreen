"""Application bulk upload request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ALLOWED_RESUME_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


class UploadFileRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=255)

    @field_validator("file_name", mode="before")
    @classmethod
    def strip_file_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_RESUME_CONTENT_TYPES:
            raise ValueError(
                "content_type must be application/pdf or "
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        return normalized


class UploadUrlsRequest(BaseModel):
    files: list[UploadFileRequest] = Field(min_length=1, max_length=50)


class UploadUrlItem(BaseModel):
    file_name: str
    s3_key: str
    upload_url: str
    expires_at: datetime


class UploadUrlsResponse(BaseModel):
    uploads: list[UploadUrlItem]


class BulkResumeItem(BaseModel):
    s3_key: str = Field(min_length=1, max_length=1024)
    file_name: str = Field(min_length=1, max_length=512)

    @field_validator("file_name", "s3_key", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class BulkCreateRequest(BaseModel):
    resumes: list[BulkResumeItem] = Field(min_length=1, max_length=50)


class BulkCreateResponse(BaseModel):
    job_id: UUID
    queued: int


class ApplicantListItem(BaseModel):
    id: UUID
    job_description_id: UUID
    candidate_id: UUID
    status: str
    source: str
    candidate_yoe: float | None = None
    resume_score: Decimal | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    created_at: datetime | None = None


class JobFitRunResponse(BaseModel):
    application_id: UUID
    status: str
    resume_score: Decimal | None = None


class ApplicationDetailResponse(BaseModel):
    id: UUID
    job_description_id: UUID
    candidate_id: UUID
    status: str
    source: str
    candidate_yoe: float | None = None
    resume_score: Decimal | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    has_resume: bool = False
    resume_file_name: str | None = None
    parsed_resume: dict | None = None
    job_fit_analysis: dict | None = None


class ApplicationResumeResponse(BaseModel):
    application_id: UUID
    file_name: str
    content_type: str
    preview_url: str
    download_url: str
    expires_at: datetime
    previewable: bool


class ApplicationRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value


class TimelineEventResponse(BaseModel):
    id: UUID
    application_id: UUID
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    actor_id: UUID | None = None
    actor_type: str
    metadata: dict | None = None
    created_at: datetime
