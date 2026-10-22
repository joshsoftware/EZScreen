"""Internal schemas for copying Attendee meeting recordings into MinIO."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

RecordingImportStatus = Literal["pending", "in_progress", "complete", "failed"]


class ScheduleRecordingImportRequest(BaseModel):
    """Sent by ai-core when the Attendee bot reaches the `ended` state."""

    bot_id: str = Field(..., min_length=1)
    import_after: datetime


class ClaimRecordingImportsRequest(BaseModel):
    limit: int = Field(default=3, ge=1, le=20)


class ClaimedRecordingImport(BaseModel):
    interview_session_id: UUID
    bot_id: str
    s3_key: str
    attempt: int


class ClaimRecordingImportsResponse(BaseModel):
    imports: list[ClaimedRecordingImport] = Field(default_factory=list)


class RecordingImportResultRequest(BaseModel):
    success: bool
    s3_key: str | None = None
    error: str | None = Field(default=None, max_length=1000)
    # False for errors a retry can't fix (e.g. Attendee has no recording).
    retryable: bool = True


class RecordingImportState(BaseModel):
    status: RecordingImportStatus
    bot_id: str
    import_after: datetime | None = None
    attempts: int = 0
    s3_key: str | None = None
    last_error: str | None = None
