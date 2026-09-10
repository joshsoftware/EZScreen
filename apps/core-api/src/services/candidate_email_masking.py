"""Staging-safe candidate email masking.

While ``SCREENING_INVITE_OVERRIDE_EMAIL`` is set, candidate addresses from resumes
are rewritten to plus-addressed variants of the *original* mailbox
(``local+<application_id>@domain``). Each application stays identifiable while
preserving the candidate's real local-part and domain.

The override address itself is only used as a default *additional* invite
recipient (see interview_session_service) — not as the stored candidate email.

Clear the setting to store and use real candidate addresses unchanged.
"""

from __future__ import annotations

from uuid import UUID

from src.config.settings import settings

__all__ = [
    "masking_enabled",
    "default_additional_invite_email",
    "mask_email_for_application",
]


def default_additional_invite_email() -> str | None:
    """Staging default additional invite recipient, or None when unset."""
    base = (settings.screening_invite_override_email or "").strip().lower()
    if not base or "@" not in base:
        return None
    return base


def masking_enabled() -> bool:
    return default_additional_invite_email() is not None


def mask_email_for_application(
    original_email: str,
    application_id: UUID | str,
) -> str | None:
    """Return ``local+<application_id>@domain`` from the resume email, or None."""
    if not masking_enabled():
        return None
    normalized = (original_email or "").strip().lower()
    if "@" not in normalized:
        return None
    local, _, domain = normalized.partition("@")
    if not local or not domain:
        return None
    # Drop any existing plus-tag so re-masking stays idempotent.
    local = local.split("+", 1)[0]
    return f"{local}+{application_id}@{domain}"
