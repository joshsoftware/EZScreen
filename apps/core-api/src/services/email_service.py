"""Outbound email helpers. Local/dev logs to console until SMTP is wired."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

from src.config.settings import settings

logger = logging.getLogger(__name__)

__all__ = [
    "ScreeningInvitePayload",
    "ScreeningInviteResult",
    "send_screening_invite",
]


@dataclass(frozen=True)
class ScreeningInvitePayload:
    to_emails: list[str]
    candidate_name: str
    job_title: str
    scheduled_at: datetime
    duration_minutes: int
    gmeet_link: str
    time_zone: str | None = None
    comment: str | None = None


class ScreeningInviteResult(TypedDict, total=False):
    sent: bool
    mode: str
    recipients: list[str]
    subject: str
    from_email: str
    reason: str


def _format_when(scheduled_at: datetime, time_zone: str | None) -> str:
    local = scheduled_at.astimezone()
    stamp = local.strftime("%a %d %b %Y, %H:%M %Z")
    if time_zone:
        return f"{stamp} ({time_zone})"
    return stamp


def _build_screening_invite_body(payload: ScreeningInvitePayload) -> str:
    when = _format_when(payload.scheduled_at, payload.time_zone)
    lines = [
        f"Hi {payload.candidate_name},",
        "",
        f"You are invited to an AI screening for {payload.job_title}.",
        "",
        f"When: {when}",
        f"Duration: {payload.duration_minutes} minutes",
        f"Meet link: {payload.gmeet_link}",
    ]
    if payload.comment:
        lines.extend(["", f"Note: {payload.comment}"])
    lines.extend(
        [
            "",
            "Please join on time using the Meet link above.",
            "",
            "— EZScreen",
        ]
    )
    return "\n".join(lines)


def send_screening_invite(payload: ScreeningInvitePayload) -> ScreeningInviteResult:
    """
    Send screening invite email.

    Dev default: log the message (EMAIL_MODE=console).
    Real SMTP/SendGrid can be added later behind EMAIL_MODE=smtp.
    """
    recipients = list(dict.fromkeys(payload.to_emails))
    subject = f"EZScreen screening invite · {payload.job_title}"
    body = _build_screening_invite_body(payload)
    mode = (getattr(settings, "email_mode", None) or "console").strip().lower()
    from_email = (settings.email_from or "noreply@ezscreen.io").strip()

    if not recipients:
        logger.warning("Screening invite skipped — no recipient emails")
        return {
            "sent": False,
            "mode": mode,
            "recipients": [],
            "subject": subject,
            "from_email": from_email,
            "reason": "no_recipients",
        }

    if mode != "console":
        # Placeholder for future providers; keep console until SMTP is configured.
        logger.warning(
            "EMAIL_MODE=%s is not implemented yet; falling back to console",
            mode,
        )
        mode = "console"

    logger.info(
        "Screening invite email (%s)\nFrom: %s\nTo: %s\nSubject: %s\n%s",
        mode,
        from_email,
        ", ".join(recipients),
        subject,
        body,
    )
    return {
        "sent": True,
        "mode": mode,
        "recipients": recipients,
        "subject": subject,
        "from_email": from_email,
    }
