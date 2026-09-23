"""Dev-only candidate email masking for invites / stored candidate addresses.

Only active when ``APP_ENV=dev`` **and** ``SCREENING_INVITE_OVERRIDE_EMAIL`` is
set. Candidate resume emails are rewritten to the *first* override mailbox with
the original address encoded in the plus-tag::

    nikhil.gosavi+jane.doe_at_acme.com@joshsoftware.com

so Meet / invite mail goes to the staging inbox, never the real candidate.

Additional override addresses (comma-separated) are still attached as extra
invite recipients. When ``APP_ENV=prod`` (or the override is empty), real
resume emails are stored and used unchanged.
"""

from __future__ import annotations

import re
from uuid import UUID

from src.config.settings import settings

__all__ = [
    "masking_enabled",
    "default_additional_invite_emails",
    "mask_email_for_application",
    "primary_invite_sink",
]

_PLUS_TAG_RE = re.compile(r"[^a-z0-9._+-]+")


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


def primary_invite_sink() -> str | None:
    """First configured override mailbox (invite sink), or None."""
    overrides = _configured_override_emails()
    return overrides[0] if overrides else None


def default_additional_invite_emails() -> list[str]:
    """Dev default additional invite recipients, or [] when disabled."""
    if not settings.is_dev:
        return []
    return _configured_override_emails()


def masking_enabled() -> bool:
    """True only in dev when at least one override mailbox is configured."""
    return bool(default_additional_invite_emails())


def _sanitize_plus_tag(email: str) -> str:
    """Encode an email for use after ``+`` (no ``@``; Gmail-safe)."""
    normalized = email.strip().lower()
    local, _, domain = normalized.partition("@")
    local = local.split("+", 1)[0]
    raw = f"{local}_at_{domain}" if domain else local
    tag = _PLUS_TAG_RE.sub("_", raw).strip("._+-")
    return (tag or "candidate")[:80]


def mask_email_for_application(
    original_email: str,
    application_id: UUID | str | None = None,
) -> str | None:
    """Rewrite candidate email to ``sink_local+candidate_at_domain@sink_domain``.

    ``application_id`` is kept for call-site compatibility; the plus-tag is the
    sanitized candidate address so staging inboxes show who was invited.
    """
    del application_id  # tag uses candidate email, not application id
    if not masking_enabled():
        return None

    sink = primary_invite_sink()
    if not sink:
        return None

    sink_local, _, sink_domain = sink.partition("@")
    sink_local = sink_local.split("+", 1)[0]
    if not sink_local or not sink_domain:
        return None

    normalized = (original_email or "").strip().lower()
    if "@" not in normalized:
        return None

    # Already rewritten onto this sink — keep stable across re-runs.
    if normalized.startswith(f"{sink_local}+") and normalized.endswith(f"@{sink_domain}"):
        return normalized

    tag = _sanitize_plus_tag(normalized)
    return f"{sink_local}+{tag}@{sink_domain}"
