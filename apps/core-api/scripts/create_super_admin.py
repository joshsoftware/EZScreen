#!/usr/bin/env python3
"""Create or update the platform super_admin user.

Usage (from apps/core-api with venv active):

    python -m scripts.create_super_admin \\
        --email admin@ezscreen.io \\
        --password 'YourSecurePassword!'

Environment overrides (optional):
    SUPER_ADMIN_EMAIL
    SUPER_ADMIN_PASSWORD
    SUPER_ADMIN_FIRST_NAME
    SUPER_ADMIN_LAST_NAME
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure apps/core-api is on sys.path when run as a script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select

from src.core.security import hash_password
from src.db.session import SessionLocal
from src.models.enums import UserRole, UserStatus
from src.models.user import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the EZScreen platform super_admin user."
    )
    parser.add_argument(
        "--email",
        default=os.getenv("SUPER_ADMIN_EMAIL", "admin@ezscreen.io"),
        help="Super admin email (default: admin@ezscreen.io or SUPER_ADMIN_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SUPER_ADMIN_PASSWORD"),
        help="Super admin password (required unless SUPER_ADMIN_PASSWORD is set)",
    )
    parser.add_argument(
        "--first-name",
        default=os.getenv("SUPER_ADMIN_FIRST_NAME", "Platform"),
        help="First name (default: Platform)",
    )
    parser.add_argument(
        "--last-name",
        default=os.getenv("SUPER_ADMIN_LAST_NAME", "Admin"),
        help="Last name (default: Admin)",
    )
    parser.add_argument(
        "--update-password",
        action="store_true",
        help="If the user already exists as super_admin, update the password",
    )
    return parser.parse_args()


def create_super_admin(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    update_password: bool = False,
) -> User:
    email_normalized = email.strip().lower()
    if not email_normalized:
        raise ValueError("Email is required")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    session = SessionLocal()
    try:
        existing = session.scalar(select(User).where(User.email == email_normalized))

        if existing is not None:
            if existing.role != UserRole.super_admin:
                raise ValueError(
                    f"User {email_normalized} already exists with role "
                    f"'{existing.role.value}'. Refuse to overwrite."
                )

            if update_password:
                existing.password_hash = hash_password(password)
                existing.first_name = first_name
                existing.last_name = last_name
                existing.status = UserStatus.active
                existing.organization_id = None
                session.commit()
                session.refresh(existing)
                print(
                    f"Updated super_admin password for {existing.email} "
                    f"(id={existing.id})"
                )
                return existing

            print(
                f"super_admin already exists: {existing.email} (id={existing.id}). "
                "No changes made. Re-run with --update-password to reset password."
            )
            return existing

        user = User(
            email=email_normalized,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.super_admin,
            status=UserStatus.active,
            organization_id=None,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Created super_admin: {user.email} (id={user.id})")
        return user
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    args = parse_args()
    if not args.password:
        print(
            "Error: password required via --password or SUPER_ADMIN_PASSWORD",
            file=sys.stderr,
        )
        return 1

    try:
        create_super_admin(
            email=args.email,
            password=args.password,
            first_name=args.first_name,
            last_name=args.last_name,
            update_password=args.update_password,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
