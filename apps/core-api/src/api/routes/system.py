"""System health and platform settings routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.deps import DbSession, require_roles
from src.config.settings import settings
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.platform import (
    HealthDetailedResponse,
    HealthStatusResponse,
    PlatformSettings,
    PlatformSettingsUpdate,
)
from src.services import platform_service

router = APIRouter(prefix="/system", tags=["System"])

SuperAdmin = Annotated[User, Depends(require_roles(UserRole.super_admin))]
OrgWorkspaceUser = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.organization_admin,
            UserRole.hr,
            UserRole.super_admin,
        )
    ),
]


@router.get("/health", summary="Service health check")
def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "core-api",
        "database_url_configured": bool(settings.database_url),
        "jwt_configured": bool(settings.jwt_secret),
    }


@router.get(
    "/health/status",
    response_model=HealthStatusResponse,
    summary="Workspace service health (Org Admin / HR)",
)
def health_status(db: DbSession, _user: OrgWorkspaceUser) -> HealthStatusResponse:
    return platform_service.get_workspace_health(db)


@router.get(
    "/health/detailed",
    response_model=HealthDetailedResponse,
    summary="Detailed platform health (Super Admin)",
)
def health_detailed(db: DbSession, _sa: SuperAdmin) -> HealthDetailedResponse:
    return platform_service.get_detailed_health(db)


@router.get(
    "/settings",
    response_model=PlatformSettings,
    summary="Platform settings (Super Admin)",
)
def get_settings(_sa: SuperAdmin) -> PlatformSettings:
    return platform_service.get_platform_settings()


@router.put(
    "/settings",
    response_model=PlatformSettings,
    summary="Update platform settings (Super Admin)",
)
def update_settings(
    body: PlatformSettingsUpdate,
    _sa: SuperAdmin,
) -> PlatformSettings:
    return platform_service.update_platform_settings(body)
