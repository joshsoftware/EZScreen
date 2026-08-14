"""Organization provisioning routes (Super Admin + Org Admin scoped)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import CurrentUser, DbSession, require_roles
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.organization import (
    OrganizationCreate,
    OrganizationDeactivateResponse,
    OrganizationResponse,
    OrganizationUpdate,
)
from src.schemas.user import OrgUserResponse, ProvisionOrgUserRequest
from src.services import organization_service, user_service

router = APIRouter(prefix="/organizations", tags=["Organizations & User Provisioning"])

SuperAdmin = Annotated[User, Depends(require_roles(UserRole.super_admin))]
SuperOrOrgAdmin = Annotated[
    User, Depends(require_roles(UserRole.super_admin, UserRole.organization_admin))
]
OrgWorkspaceUser = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.super_admin, UserRole.organization_admin, UserRole.hr
        )
    ),
]


def _to_org_response(
    org,
    stats: dict[str, int] | None = None,
) -> OrganizationResponse:
    stats = stats or {}
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        domain=org.domain,
        logo_url=org.logo_url,
        is_active=org.is_active,
        created_at=org.created_at,
        user_count=stats.get("user_count", 0),
        job_count=stats.get("job_count", 0),
        application_count=stats.get("application_count", 0),
    )


def _assert_org_access(user: User, organization_id: UUID) -> None:
    if user.role == UserRole.super_admin:
        return
    if user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another organization",
        )


@router.get(
    "",
    response_model=list[OrganizationResponse],
    summary="List all organizations (Super Admin only)",
)
def list_organizations(
    db: DbSession,
    _sa: SuperAdmin,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    q: str | None = None,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="active | suspended | all",
    ),
) -> list[OrganizationResponse]:
    active: bool | None = None
    if status_filter == "active":
        active = True
    elif status_filter in ("suspended", "inactive"):
        active = False

    orgs = organization_service.list_organizations(
        db, page=page, limit=limit, q=q, active=active
    )
    counts = organization_service.organization_counts_map(db)
    return [
        _to_org_response(org, counts.get(org.id, {}))
        for org in orgs
    ]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Super Admin creates a new organization",
)
def create_organization(
    body: OrganizationCreate,
    db: DbSession,
    _sa: SuperAdmin,
) -> OrganizationResponse:
    try:
        org = organization_service.create_organization(db, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _to_org_response(org, {"user_count": 0, "job_count": 0, "application_count": 0})


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="View organization details",
)
def get_organization(
    organization_id: UUID,
    db: DbSession,
    current_user: OrgWorkspaceUser,
) -> OrganizationResponse:
    _assert_org_access(current_user, organization_id)
    org = organization_service.get_organization(db, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    stats = organization_service.organization_stats(db, organization_id)
    return _to_org_response(org, stats)


@router.put(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Update organization details",
)
def update_organization(
    organization_id: UUID,
    body: OrganizationUpdate,
    db: DbSession,
    current_user: SuperOrOrgAdmin,
) -> OrganizationResponse:
    _assert_org_access(current_user, organization_id)
    # Org admin may not hard-suspend via this path unless super admin
    if (
        current_user.role != UserRole.super_admin
        and body.is_active is not None
        and body.is_active is False
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can suspend organizations",
        )

    org = organization_service.get_organization(db, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    try:
        org = organization_service.update_organization(db, org, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    stats = organization_service.organization_stats(db, organization_id)
    return _to_org_response(org, stats)


@router.delete(
    "/{organization_id}",
    response_model=OrganizationDeactivateResponse,
    summary="Soft delete / deactivate organization",
)
def delete_organization(
    organization_id: UUID,
    db: DbSession,
    _sa: SuperAdmin,
) -> OrganizationDeactivateResponse:
    org = organization_service.get_organization(db, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org = organization_service.deactivate_organization(db, org)
    return OrganizationDeactivateResponse(
        id=org.id,
        is_active=org.is_active,
        message="Organization deactivated",
    )


@router.get(
    "/{organization_id}/users",
    response_model=list[OrgUserResponse],
    summary="List users belonging to an organization",
)
def list_org_users(
    organization_id: UUID,
    db: DbSession,
    current_user: SuperOrOrgAdmin,
) -> list[OrgUserResponse]:
    _assert_org_access(current_user, organization_id)
    org = organization_service.get_organization(db, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    users = user_service.list_org_users(db, organization_id)
    return [OrgUserResponse.model_validate(u) for u in users]


@router.post(
    "/{organization_id}/users",
    response_model=OrgUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision Organization Admin or HR users",
)
def provision_org_user(
    organization_id: UUID,
    body: ProvisionOrgUserRequest,
    db: DbSession,
    current_user: SuperOrOrgAdmin,
) -> OrgUserResponse:
    _assert_org_access(current_user, organization_id)

    org = organization_service.get_organization(db, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot provision users for a suspended organization",
        )

    try:
        user, temp_password = user_service.provision_org_user(
            db, organization_id=organization_id, data=body
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    response = OrgUserResponse.model_validate(user)
    response.temporary_password = temp_password
    return response
