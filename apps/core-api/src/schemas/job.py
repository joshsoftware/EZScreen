"""Job description request/response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import JobStatus, JobType, WorkType


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    job_type: JobType | None = None
    work_type: WorkType | None = None
    location: str | None = Field(default=None, max_length=255)
    experience_min: int | None = Field(default=None, ge=0, le=50)
    experience_max: int | None = Field(default=None, ge=0, le=50)
    skills: str | None = None
    status: JobStatus = JobStatus.draft
    organization_id: UUID | None = None

    @field_validator("title", "description", "location", "skills", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    job_type: JobType | None = None
    work_type: WorkType | None = None
    location: str | None = Field(default=None, max_length=255)
    experience_min: int | None = Field(default=None, ge=0, le=50)
    experience_max: int | None = Field(default=None, ge=0, le=50)
    skills: str | None = None
    status: JobStatus | None = None

    @field_validator("title", "description", "location", "skills", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by: UUID
    title: str | None
    job_type: JobType | None
    work_type: WorkType | None
    location: str | None
    experience_min: int | None
    experience_max: int | None
    skills: str | None
    status: JobStatus


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by: UUID
    title: str | None
    description: str | None
    job_type: JobType | None
    work_type: WorkType | None
    location: str | None
    experience_min: int | None
    experience_max: int | None
    skills: str | None
    status: JobStatus


class JobUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    status: JobStatus
