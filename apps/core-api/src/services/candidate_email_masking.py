"""Dev-only candidate email masking.

Only active when ``APP_ENV=dev`` **and** ``SCREENING_INVITE_OVERRIDE_EMAIL`` is
set. In that case candidate addresses from resumes are rewritten to
plus-addressed variants of the *original* mailbox
(``local+<application_id>@domain``).

The override address(es) themselves are only used as default *additional*
invite recipients (see interview_session_service) — not as the stored
candidate email. Comma-separated values are supported.

When ``APP_ENV=prod`` (or the override is empty), real resume emails are stored
and used unchanged.
"""

from __future__ import annotations

from uuid import UUID

from src.config.settings import settings

__all__ = [
    "masking_enabled",
    "default_additional_invite_emails",
    "mask_email_for_application",
]


def _configured_override_emails() -> list[str]:
    raw = (settings.screening_invite_override_email or "").strip().lower()
    if not raw:
        return []
    emails: list[str] = []
    for part in raw.replace(";", ",").split(","):
        email = part.strip()
        if email and "@" in email:
            emails.append(email)
    return list(dict.fromkeys(emails))


def default_additional_invite_emails() -> list[str]:
    """Dev default additional invite recipients, or [] when disabled."""
    if not settings.is_dev:
        return []
    return _configured_override_emails()


def masking_enabled() -> bool:
    """True only in dev when at least one override mailbox is configured."""
    return bool(default_additional_invite_emails())


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
