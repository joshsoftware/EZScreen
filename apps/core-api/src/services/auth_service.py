"""Authentication business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.jwt import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.core.security import verify_password
from src.models.enums import UserRole, UserStatus
from src.models.organization import Organization
from src.models.refresh_token_revocation import RefreshTokenRevocation
from src.models.user import User

__all__ = [
    "OrgAuthError",
    "OrgAuthFailure",
    "authenticate_user",
    "authenticate_org_workspace_user",
    "get_user_by_id",
    "get_user_by_email",
    "issue_token_pair",
    "refresh_access_token",
    "revoke_refresh_token",
]

_ORG_WORKSPACE_ROLES = frozenset({UserRole.organization_admin, UserRole.hr})


class OrgAuthFailure(str, Enum):
    invalid_credentials = "invalid_credentials"
    wrong_role = "wrong_role"
    org_missing = "org_missing"
    org_suspended = "org_suspended"


@dataclass(frozen=True)
class OrgAuthError:
    failure: OrgAuthFailure
    detail: str


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    return db.scalar(select(User).where(User.email == normalized))


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return active user if credentials match; otherwise None."""
    user = get_user_by_email(db, email)
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status != UserStatus.active:
        return None
    return user


def authenticate_org_workspace_user(
    db: Session, email: str, password: str
) -> User | OrgAuthError:
    """Authenticate for Organization Admin portal (organization_admin or hr)."""
    user = authenticate_user(db, email, password)
    if user is None:
        return OrgAuthError(
            failure=OrgAuthFailure.invalid_credentials,
            detail="Invalid email or password",
        )

    if user.role not in _ORG_WORKSPACE_ROLES:
        return OrgAuthError(
            failure=OrgAuthFailure.wrong_role,
            detail="Organization workspace access only",
        )

    if user.organization_id is None:
        return OrgAuthError(
            failure=OrgAuthFailure.org_missing,
            detail="Organization not found",
        )

    org = db.get(Organization, user.organization_id)
    if org is None:
        return OrgAuthError(
            failure=OrgAuthFailure.org_missing,
            detail="Organization not found",
        )
    if not org.is_active:
        return OrgAuthError(
            failure=OrgAuthFailure.org_suspended,
            detail="Organization is suspended",
        )

    return user


def issue_token_pair(db: Session, user: User) -> tuple[str, int, str]:
    """Mint access + refresh tokens; touch last_login_at. Returns (access, expires_in, refresh)."""
    access_token, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        organization_id=user.organization_id,
    )
    refresh_token, _, _ = create_refresh_token(user_id=user.id)
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return access_token, expires_in, refresh_token


def _is_refresh_revoked(db: Session, jti: str) -> bool:
    return db.get(RefreshTokenRevocation, jti) is not None


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a refresh token by JTI (logout)."""
    try:
        payload = decode_refresh_token(refresh_token)
    except TokenError:
        return

    jti = payload["jti"]
    if _is_refresh_revoked(db, jti):
        return

    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc)

    db.add(
        RefreshTokenRevocation(
            jti=jti,
            user_id=UUID(payload["sub"]),
            expires_at=expires_at,
        )
    )
    db.commit()


def refresh_access_token(
    db: Session, refresh_token: str
) -> tuple[str, int, str, User]:
    """Validate refresh cookie, rotate refresh token, return new access + refresh + user."""
    payload = decode_refresh_token(refresh_token)
    jti = payload["jti"]
    user_id = UUID(payload["sub"])

    if _is_refresh_revoked(db, jti):
        raise TokenError("Refresh token revoked")

    user = get_user_by_id(db, user_id)
    if user is None or user.status != UserStatus.active:
        raise TokenError("User not found or inactive")

    revoke_refresh_token(db, refresh_token)

    access_token, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        organization_id=user.organization_id,
    )
    new_refresh, _, _ = create_refresh_token(user_id=user.id)
    return access_token, expires_in, new_refresh, user
