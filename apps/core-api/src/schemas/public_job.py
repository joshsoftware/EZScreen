"""Public candidate job request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models.enums import JobType, WorkType
from src.schemas.job import JobSkills


class PublicJobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    organization_name: str | None = None
    organization_domain: str | None = None
    organization_logo_url: str | None = None
    title: str | None = None
    job_type: JobType | None = None
    work_type: WorkType | None = None
    location: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    skills: JobSkills | dict | str | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None


class PublicJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    organization_name: str | None = None
    organization_domain: str | None = None
    organization_logo_url: str | None = None
    title: str | None = None
    description: str | None = None
    job_type: JobType | None = None
    work_type: WorkType | None = None
    location: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    skills: JobSkills | dict | str | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None
