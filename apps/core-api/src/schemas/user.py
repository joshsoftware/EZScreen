"""User provisioning schemas for organizations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import UserRole, UserStatus


class ProvisionOrgUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=8)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    role: UserRole = UserRole.organization_admin

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("Invalid email address")
        return email

    @field_validator("role")
    @classmethod
    def allowed_roles(cls, value: UserRole) -> UserRole:
        if value not in (UserRole.organization_admin, UserRole.hr):
            raise ValueError("Only organization_admin or hr can be provisioned")
        return value


class OrgUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    role: UserRole
    email: str
    first_name: str | None
    last_name: str | None
    phone: str | None
    status: UserStatus
    temporary_password: str | None = None
