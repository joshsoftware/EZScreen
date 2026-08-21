"""Platform health checks and settings storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.application import Application
from src.models.job_description import JobDescription
from src.models.organization import Organization
from src.models.user import User
from src.schemas.platform import (
    HealthDetailedResponse,
    PlatformSettings,
    PlatformSettingsUpdate,
    ServiceStatus,
)

__all__ = ["get_detailed_health", "get_platform_settings", "update_platform_settings"]

_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "platform_settings.json"
_APP_STARTED_AT = datetime.now(timezone.utc)


def _check_database(db: Session) -> ServiceStatus:
    try:
        db.execute(text("SELECT 1"))
        return ServiceStatus(
            name="PostgreSQL",
            detail="primary database",
            status="healthy",
        )
    except Exception as exc:  # noqa: BLE001 — surface as health status
        return ServiceStatus(
            name="PostgreSQL",
            detail=str(exc)[:120],
            status="down",
        )


def get_detailed_health(db: Session) -> HealthDetailedResponse:
    database = _check_database(db)
    org_count = db.scalar(select(func.count(Organization.id))) or 0
    user_count = db.scalar(select(func.count(User.id))) or 0
    job_count = db.scalar(select(func.count(JobDescription.id))) or 0
    app_count = db.scalar(select(func.count(Application.id))) or 0

    uptime_seconds = int((datetime.now(timezone.utc) - _APP_STARTED_AT).total_seconds())
    overall = "healthy" if database.status == "healthy" else "degraded"

    services_note = (
        "Workers and Attendee bot are not deployed yet — shown as pending/healthy stub."
    )

    events: list[dict[str, str]] = [
        {
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "message": f"Health check · {org_count} orgs · {user_count} users",
        },
        {
            "time": _APP_STARTED_AT.strftime("%H:%M"),
            "message": "Core API process started",
        },
    ]

    return HealthDetailedResponse(
        status=overall,
        service="core-api",
        database=database,
        api=ServiceStatus(
            name="API gateway",
            detail="core-api local",
            status="healthy",
        ),
        parse_workers=ServiceStatus(
            name="Parse workers (JD / resume)",
            detail=services_note,
            status="healthy",
        ),
        screening_bot=ServiceStatus(
            name="Screening bot dispatch",
            detail="Attendee integration not configured",
            status="degraded",
        ),
        object_storage=ServiceStatus(
            name="Object storage (S3)",
            detail="MinIO / S3 not required for platform ops API",
            status="healthy",
        ),
        stats={
            "organizations": org_count,
            "users": user_count,
            "jobs": job_count,
            "applications": app_count,
            "uptime_seconds": uptime_seconds,
            "jwt_ttl_minutes": settings.access_token_expire_minutes,
        },
        recent_events=events,
    )


def get_platform_settings() -> PlatformSettings:
    if _SETTINGS_PATH.exists():
        try:
            data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            return PlatformSettings.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return PlatformSettings()


def update_platform_settings(payload: PlatformSettingsUpdate) -> PlatformSettings:
    current = get_platform_settings()
    updated = current.model_copy(
        update=payload.model_dump(exclude_unset=True),
    )
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(
        updated.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return updated
