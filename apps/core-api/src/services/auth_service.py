"""Authentication business logic."""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.jwt import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.core.security import hash_password, verify_password
from src.models.enums import UserRole, UserStatus
from src.models.organization import Organization
from src.models.password_reset_token import PasswordResetToken
from src.models.refresh_token_revocation import RefreshTokenRevocation
from src.models.user import User

logger = logging.getLogger(__name__)

__all__ = [
    "OrgAuthError",
    "OrgAuthFailure",
    "authenticate_user",
    "authenticate_org_workspace_user",
    "change_password",
    "get_user_by_id",
    "get_user_by_email",
    "issue_token_pair",
    "refresh_access_token",
    "request_org_password_reset",
    "reset_password_with_token",
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


def _revocation_expires_at(payload: dict) -> datetime:
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _insert_refresh_revocation(
    db: Session, jti: str, user_id: UUID, expires_at: datetime
) -> bool:
    """Insert revocation row. Returns True if newly revoked, False if already revoked."""
    stmt = (
        insert(RefreshTokenRevocation)
        .values(jti=jti, user_id=user_id, expires_at=expires_at)
        .on_conflict_do_nothing(index_elements=["jti"])
        .returning(RefreshTokenRevocation.jti)
    )
    inserted = db.scalar(stmt)
    db.commit()
    return inserted is not None


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a refresh token by JTI (logout). Idempotent."""
    try:
        payload = decode_refresh_token(refresh_token)
    except TokenError:
        return

    _insert_refresh_revocation(
        db,
        payload["jti"],
        UUID(payload["sub"]),
        _revocation_expires_at(payload),
    )


def refresh_access_token(
    db: Session, refresh_token: str
) -> tuple[str, int, str, User]:
    """Validate refresh cookie, rotate refresh token, return new access + refresh + user."""
    payload = decode_refresh_token(refresh_token)
    jti = payload["jti"]
    user_id = UUID(payload["sub"])

    user = get_user_by_id(db, user_id)
    if user is None or user.status != UserStatus.active:
        raise TokenError("User not found or inactive")

    if not _insert_refresh_revocation(
        db, jti, user_id, _revocation_expires_at(payload)
    ):
        raise TokenError("Refresh token revoked")

    access_token, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        organization_id=user.organization_id,
    )
    new_refresh, _, _ = create_refresh_token(user_id=user.id)
    return access_token, expires_in, new_refresh, user


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def change_password(
    db: Session, user: User, current_password: str, new_password: str
) -> None:
    """Update password for an authenticated org workspace user."""
    if user.role not in _ORG_WORKSPACE_ROLES:
        raise ValueError("Organization workspace access only")
    if not user.password_hash or not verify_password(current_password, user.password_hash):
        raise PermissionError("Current password is incorrect")
    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters")
    if verify_password(new_password, user.password_hash):
        raise ValueError("New password must be different from the current password")

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()


def request_org_password_reset(db: Session, email: str) -> str | None:
    """
    Create a password reset token for org_admin/hr if the account exists.
    Returns reset_url when password_reset_expose_link is enabled (local/dev);
    otherwise None. Callers must always show a generic success message.
    """
    user = get_user_by_email(db, email)
    if (
        user is None
        or user.status != UserStatus.active
        or user.role not in _ORG_WORKSPACE_ROLES
        or not user.password_hash
    ):
        return None

    # Invalidate unused tokens for this user
    now = datetime.now(timezone.utc)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=settings.password_reset_expire_minutes)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=expires_at,
        )
    )
    db.commit()

    reset_path = f"/org-admin/reset-password?token={raw_token}"
    base = settings.frontend_base_url.rstrip("/")
    reset_url = f"{base}{reset_path}"
    logger.info("Password reset link for %s: %s", user.email, reset_url)
    return reset_url if settings.password_reset_expose_link else None


def reset_password_with_token(db: Session, raw_token: str, new_password: str) -> None:
    """Consume a one-time reset token and set a new password."""
    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters")

    token_hash = _hash_reset_token(raw_token.strip())
    row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or row.expires_at < now:
        raise PermissionError("Invalid or expired reset link")

    user = get_user_by_id(db, row.user_id)
    if (
        user is None
        or user.status != UserStatus.active
        or user.role not in _ORG_WORKSPACE_ROLES
    ):
        raise PermissionError("Invalid or expired reset link")

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    row.used_at = now
    db.add(user)
    db.add(row)
    db.commit()
