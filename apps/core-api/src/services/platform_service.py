"""Platform health checks and settings storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.application import Application
from src.models.job_description import JobDescription
from src.models.organization import Organization
from src.models.user import User
from src.schemas.platform import (
    HealthDetailedResponse,
    HealthStatusResponse,
    PlatformSettings,
    PlatformSettingsUpdate,
    ServiceStatus,
)
from src.services.storage_service import _s3_client

__all__ = [
    "get_detailed_health",
    "get_workspace_health",
    "get_platform_settings",
    "update_platform_settings",
]

_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "platform_settings.json"
_APP_STARTED_AT = datetime.now(timezone.utc)
_HEALTH_TIMEOUT_SECONDS = 5.0


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


def _check_ai_core_services() -> ServiceStatus:
    url = f"{settings.ai_services_base_url.rstrip('/')}/health"
    try:
        with httpx.Client(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        return ServiceStatus(
            name="AI core services",
            detail=f"{url} — {exc}"[:120],
            status="down",
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(
            name="AI core services",
            detail=str(exc)[:120],
            status="down",
        )

    if not isinstance(payload, dict):
        return ServiceStatus(
            name="AI core services",
            detail=f"{url} returned invalid payload",
            status="degraded",
        )

    service_name = str(payload.get("service") or "ai-core-services")
    environment = str(payload.get("environment") or "unknown")
    modules = payload.get("modules")
    module_count = len(modules) if isinstance(modules, list) else 0
    detail = f"{service_name} · {environment} · {module_count} modules"

    if payload.get("status") == "healthy":
        return ServiceStatus(name="AI core services", detail=detail, status="healthy")

    return ServiceStatus(
        name="AI core services",
        detail=f"{detail} · status={payload.get('status', 'unknown')}"[:120],
        status="degraded",
    )


def _check_object_storage() -> ServiceStatus:
    bucket = settings.minio_bucket_resumes
    endpoint = settings.minio_internal_endpoint or settings.minio_endpoint
    try:
        client = _s3_client(internal=True)
        client.head_bucket(Bucket=bucket)
        return ServiceStatus(
            name="Object storage (MinIO)",
            detail=f"{endpoint} · bucket {bucket}",
            status="healthy",
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(
            name="Object storage (MinIO)",
            detail=f"{endpoint} · {exc}"[:120],
            status="down",
        )


def _check_screening_bot() -> ServiceStatus:
    return ServiceStatus(
        name="Screening bot (Attendee)",
        detail="Not configured — scheduling uses mock Meet links",
        status="degraded",
    )


def _overall_status(*services: ServiceStatus) -> str:
    if any(service.status == "down" for service in services):
        return "degraded"
    if any(service.status == "degraded" for service in services):
        return "degraded"
    return "healthy"


def get_detailed_health(db: Session) -> HealthDetailedResponse:
    database = _check_database(db)
    ai_core = _check_ai_core_services()
    object_storage = _check_object_storage()
    screening_bot = _check_screening_bot()

    org_count = db.scalar(select(func.count(Organization.id))) or 0
    user_count = db.scalar(select(func.count(User.id))) or 0
    job_count = db.scalar(select(func.count(JobDescription.id))) or 0
    app_count = db.scalar(select(func.count(Application.id))) or 0

    uptime_seconds = int((datetime.now(timezone.utc) - _APP_STARTED_AT).total_seconds())
    checked_at = datetime.now(timezone.utc).isoformat()

    api = ServiceStatus(
        name="Core API",
        detail="core-api gateway",
        status="healthy",
    )

    overall = _overall_status(database, api, ai_core, object_storage, screening_bot)
    if database.status == "down":
        overall = "degraded"

    down_services = [
        service.name
        for service in (database, ai_core, object_storage)
        if service.status == "down"
    ]
    status_note = (
        f"Unavailable: {', '.join(down_services)}"
        if down_services
        else "All critical services responding"
    )

    events: list[dict[str, str]] = [
        {
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "message": f"Health check · {status_note}",
        },
        {
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "message": f"{org_count} orgs · {user_count} users · {job_count} jobs",
        },
        {
            "time": _APP_STARTED_AT.strftime("%H:%M"),
            "message": "Core API process started",
        },
    ]

    return HealthDetailedResponse(
        status=overall,
        service="core-api",
        checked_at=checked_at,
        database=database,
        api=api,
        ai_core_services=ai_core,
        parse_workers=ai_core,
        screening_bot=screening_bot,
        object_storage=object_storage,
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


def get_workspace_health(db: Session) -> HealthStatusResponse:
    """Health summary for org HR/admin — critical dependencies only."""
    database = _check_database(db)
    ai_core = _check_ai_core_services()
    object_storage = _check_object_storage()
    services = [database, ai_core, object_storage]
    overall = _overall_status(*services)
    if database.status == "down":
        overall = "degraded"

    return HealthStatusResponse(
        status=overall,
        checked_at=datetime.now(timezone.utc).isoformat(),
        services=services,
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
