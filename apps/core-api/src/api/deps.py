"""FastAPI dependencies: database session, current user, role guards."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.jwt import TokenError, decode_access_token
from src.db.session import SessionLocal
from src.models.enums import UserRole, UserStatus
from src.models.user import User
from src.services.auth_service import get_user_by_id

__all__ = [
    "DbSession",
    "CurrentUser",
    "get_db",
    "get_current_user",
    "require_roles",
    "verify_internal_service",
]

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (TokenError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = get_user_by_id(db, user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory that allows only the listed roles."""

    allowed = set(roles)

    def _checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _checker


def verify_internal_service(
    x_internal_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Guard screening pipeline callbacks from ai-core-services."""
    expected = settings.internal_service_token
    if not expected:
        return
    if x_internal_service_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )
