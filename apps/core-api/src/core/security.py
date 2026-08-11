"""Password hashing utilities shared by scripts and auth services."""

from passlib.context import CryptContext

__all__ = ["hash_password", "verify_password"]

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash for the given plain-text password."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if plain_text matches the stored hash."""
    if not password_hash:
        return False
    return _pwd_context.verify(plain_password, password_hash)
