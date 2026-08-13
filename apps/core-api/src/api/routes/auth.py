"""Authentication routes: login, refresh, me, logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.api.deps import CurrentUser, DbSession, require_roles
from src.core.cookies import clear_refresh_cookie, set_refresh_cookie
from src.core.jwt import TokenError
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshResponse,
    UserResponse,
)
from src.config.settings import settings
from src.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate user & receive JWT access token (platform / shared login)",
)
def login(body: LoginRequest, db: DbSession, response: Response) -> LoginResponse:
    user = auth_service.authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token, expires_in, refresh_token = auth_service.issue_token_pair(db, user)
    set_refresh_cookie(response, refresh_token)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Issue a new access token using the httpOnly refresh cookie",
)
def refresh(
    request: Request,
    db: DbSession,
    response: Response,
) -> RefreshResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        access_token, expires_in, new_refresh, _user = auth_service.refresh_access_token(
            db, refresh_token
        )
    except TokenError as exc:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    set_refresh_cookie(response, new_refresh)
    return RefreshResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve current authenticated user profile",
)
def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke refresh session and logout",
)
def logout(
    request: Request,
    db: DbSession,
    response: Response,
    _current_user: CurrentUser,
) -> MessageResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        auth_service.revoke_refresh_token(db, refresh_token)
    clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


@router.post(
    "/org/login",
    response_model=LoginResponse,
    summary="Authenticate Organization Admin or HR for workspace access",
)
def org_login(body: LoginRequest, db: DbSession, response: Response) -> LoginResponse:
    result = auth_service.authenticate_org_workspace_user(db, body.email, body.password)
    if isinstance(result, auth_service.OrgAuthError):
        if result.failure == auth_service.OrgAuthFailure.invalid_credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.detail,
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.detail,
        )

    access_token, expires_in, refresh_token = auth_service.issue_token_pair(db, result)
    set_refresh_cookie(response, refresh_token)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(result),
    )


@router.get(
    "/org/check",
    response_model=MessageResponse,
    summary="Verify Organization Admin or HR token and role",
)
def org_workspace_check(
    _user: Annotated[
        User,
        Depends(require_roles(UserRole.organization_admin, UserRole.hr)),
    ],
) -> MessageResponse:
    return MessageResponse(message="Organization workspace access confirmed")


# Super-admin-only smoke route — confirms role guard for platform login flow.
@router.get(
    "/super-admin/check",
    response_model=MessageResponse,
    summary="Verify Super Admin token and role",
)
def super_admin_check(
    _user: Annotated[User, Depends(require_roles(UserRole.super_admin))],
) -> MessageResponse:
    return MessageResponse(message="Super admin access confirmed")
