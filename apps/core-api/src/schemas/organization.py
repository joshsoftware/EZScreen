"""Organization request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    logo_url: str | None = None

    @field_validator("name", "domain", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        domain = value.lower().removesuffix(".ezscreen.io")
        if not domain.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Domain must be alphanumeric (hyphens/underscores allowed)")
        return domain


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    logo_url: str | None = None
    is_active: bool | None = None

    @field_validator("name", "domain", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value == "":
            return None
        domain = value.lower().removesuffix(".ezscreen.io")
        if not domain.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Domain must be alphanumeric (hyphens/underscores allowed)")
        return domain


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str | None
    logo_url: str | None
    is_active: bool
    created_at: datetime | None = None
    user_count: int = 0
    job_count: int = 0
    application_count: int = 0


class OrganizationDeactivateResponse(BaseModel):
    id: UUID
    is_active: bool
    message: str
