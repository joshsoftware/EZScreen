"""Platform health and settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    name: str
    detail: str
    status: str  # healthy | degraded | down


class HealthDetailedResponse(BaseModel):
    status: str
    service: str
    checked_at: str
    database: ServiceStatus
    api: ServiceStatus
    ai_core_services: ServiceStatus
    parse_workers: ServiceStatus  # alias of ai_core_services (backward compat)
    screening_bot: ServiceStatus
    object_storage: ServiceStatus
    stats: dict[str, int | float | str]
    recent_events: list[dict[str, str]]


class HealthStatusResponse(BaseModel):
    """Lightweight health for org HR / admin workspace."""

    status: str
    checked_at: str
    services: list[ServiceStatus]


class PlatformSettings(BaseModel):
    platform_name: str = "EZScreen"
    support_email: str = "support@ezscreen.io"
    timezone: str = "Asia/Kolkata"
    extraction_model: str = "gemma-parse-v2"
    screening_model: str = "gemma-screen-v3"
    auto_retry_failed_jobs: bool = True
    require_mfa_super_admin: bool = True
    invite_expiry_days: int = Field(default=7, ge=1, le=90)


class PlatformSettingsUpdate(BaseModel):
    platform_name: str | None = Field(default=None, min_length=1, max_length=100)
    support_email: str | None = None
    timezone: str | None = None
    extraction_model: str | None = None
    screening_model: str | None = None
    auto_retry_failed_jobs: bool | None = None
    require_mfa_super_admin: bool | None = None
    invite_expiry_days: int | None = Field(default=None, ge=1, le=90)
