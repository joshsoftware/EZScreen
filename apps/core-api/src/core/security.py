"""Password hashing utilities shared by scripts and auth services."""

from __future__ import annotations

import bcrypt

__all__ = ["hash_password", "verify_password"]


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash for the given plain-text password."""
    hashed = bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt(),
    )
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if plain text matches the stored hash."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
