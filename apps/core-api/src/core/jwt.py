"""JWT create/decode helpers for access and refresh tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt

from src.config.settings import settings

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    "TokenError",
]

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenError(Exception):
    """Raised when a JWT is missing, invalid, or expired."""


def create_access_token(
    *,
    user_id: UUID,
    email: str,
    role: str,
    organization_id: UUID | None,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """Return (encoded_jwt, expires_in_seconds)."""
    expire_minutes = expires_minutes or settings.access_token_expire_minutes
    expires_delta = timedelta(minutes=expire_minutes)
    expire_at = datetime.now(timezone.utc) + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "organization_id": str(organization_id) if organization_id else None,
        "type": TOKEN_TYPE_ACCESS,
        "exp": expire_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, int(expires_delta.total_seconds())


def create_refresh_token(*, user_id: UUID) -> tuple[str, str, datetime]:
    """Return (encoded_jwt, jti, expires_at)."""
    jti = str(uuid4())
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    expire_at = datetime.now(timezone.utc) + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": TOKEN_TYPE_REFRESH,
        "jti": jti,
        "exp": expire_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti, expire_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token. Raises TokenError on failure."""
    payload = _decode_token(token)
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise TokenError("Invalid token type")
    if not payload.get("sub"):
        raise TokenError("Invalid token payload")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode and validate a refresh token. Raises TokenError on failure."""
    payload = _decode_token(token)
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise TokenError("Invalid token type")
    if not payload.get("sub") or not payload.get("jti"):
        raise TokenError("Invalid token payload")
    return payload


def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise TokenError("Invalid or expired token") from exc
