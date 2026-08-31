"""Job description request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.enums import JobStatus, JobType, WorkType


class SkillItem(BaseModel):
    skill: str = Field(min_length=1, max_length=255)
    required_years: float | None = Field(default=None, ge=0, le=50)

    @field_validator("skill", mode="before")
    @classmethod
    def strip_skill(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class JobSkills(BaseModel):
    must_have: list[SkillItem] = Field(default_factory=list)
    good_to_have: list[SkillItem] = Field(default_factory=list)

    @field_validator("must_have", "good_to_have", mode="before")
    @classmethod
    def coerce_skill_items(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        items: list[object] = []
        for item in value:
            if isinstance(item, str):
                items.append({"skill": item, "required_years": None})
            else:
                items.append(item)
        return items


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    job_type: JobType | None = None
    work_type: WorkType | None = None
    location: str | None = Field(default=None, max_length=255)
    experience_min: int | None = Field(default=None, ge=0, le=50)
    experience_max: int | None = Field(default=None, ge=0, le=50)
    skills: JobSkills | None = None
    status: JobStatus = JobStatus.draft
    organization_id: UUID | None = None

    @field_validator("title", "description", "location", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def check_experience_range(self) -> JobCreate:
        if (
            self.experience_min is not None
            and self.experience_max is not None
            and self.experience_min > self.experience_max
        ):
            raise ValueError("Minimum experience cannot be greater than maximum")
        return self


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    job_type: JobType | None = None
    work_type: WorkType | None = None
    location: str | None = Field(default=None, max_length=255)
    experience_min: int | None = Field(default=None, ge=0, le=50)
    experience_max: int | None = Field(default=None, ge=0, le=50)
    skills: JobSkills | None = None
    status: JobStatus | None = None

    @field_validator("title", "description", "location", mode="before")
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
    skills: JobSkills | None = None
    status: JobStatus
    created_at: datetime | None = None
    applicant_count: int = 0


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
    skills: JobSkills | None = None
    status: JobStatus
    parsed_jd: dict | None = None
    screening_questions: dict | None = None


class JobUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    status: JobStatus
    skills: JobSkills | None = None
    screening_questions: dict | None = None


class ScreeningQuestionItem(BaseModel):
    id: int | None = None
    category: str = Field(default="must_have", max_length=64)
    skill_focus: str = Field(default="", max_length=255)
    question: str = Field(min_length=1, max_length=4000)
    expected_keywords: list[str] = Field(default_factory=list)
    answer_depth: str = Field(default="partial_depth", max_length=32)

    @field_validator("skill_focus", "question", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("expected_keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value


class ScreeningQuestionsUpdate(BaseModel):
    questions: list[ScreeningQuestionItem] = Field(default_factory=list)
