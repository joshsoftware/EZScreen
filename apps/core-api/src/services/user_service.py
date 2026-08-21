"""Organization user provisioning."""

from __future__ import annotations

import secrets
import string
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.security import hash_password
from src.models.enums import UserRole, UserStatus
from src.models.user import User
from src.schemas.user import ProvisionOrgUserRequest

__all__ = ["list_org_users", "provision_org_user"]


def list_org_users(db: Session, organization_id: UUID) -> list[User]:
    stmt = (
        select(User)
        .where(User.organization_id == organization_id)
        .order_by(User.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def _generate_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def provision_org_user(
    db: Session,
    *,
    organization_id: UUID,
    data: ProvisionOrgUserRequest,
) -> tuple[User, str | None]:
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise ValueError("A user with this email already exists")

    temporary_password: str | None = None
    raw_password = data.password
    if not raw_password:
        temporary_password = _generate_password()
        raw_password = temporary_password

    user = User(
        organization_id=organization_id,
        email=data.email,
        password_hash=hash_password(raw_password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        role=data.role,
        status=UserStatus.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, temporary_password
