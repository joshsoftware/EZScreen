"""Google Meet join links for screening (Spaces API only — no Calendar)."""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime
from typing import TypedDict
from uuid import uuid4

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

__all__ = [
    "ScreeningMeetResult",
    "create_screening_meet",
]

_SCOPES = ("https://www.googleapis.com/auth/meetings.space.created",)
_MEET_SPACES_URL = "https://meet.googleapis.com/v2/spaces"
_MEET_CODE_ALPHABET = string.ascii_lowercase


class ScreeningMeetResult(TypedDict, total=False):
    gmeet_link: str
    meet_space_name: str | None
    meeting_code: str | None
    duration_minutes: int
    time_zone: str | None
    scheduled_at: str
    provider: str
    attendees: list[str]


def _meet_mode() -> str:
    return (settings.google_meet_mode or "mock").strip().lower()


def _mock_meet_code() -> str:
    def chunk(n: int) -> str:
        return "".join(secrets.choice(_MEET_CODE_ALPHABET) for _ in range(n))

    return f"{chunk(3)}-{chunk(4)}-{chunk(3)}"


def _create_mock_meet(
    *,
    scheduled_at: datetime,
    duration_minutes: int,
    time_zone: str | None,
    attendees: list[str] | None = None,
) -> ScreeningMeetResult:
    code = _mock_meet_code()
    link = f"https://meet.google.com/{code}"
    guest_emails = list(dict.fromkeys(attendees or []))
    logger.info(
        "GOOGLE_MEET_MODE=mock — placeholder Meet link %s (attendees=%s)",
        link,
        guest_emails,
    )
    return {
        "gmeet_link": link,
        "meet_space_name": f"spaces/mock-{uuid4()}",
        "meeting_code": code,
        "duration_minutes": duration_minutes,
        "time_zone": time_zone,
        "scheduled_at": scheduled_at.isoformat(),
        "provider": "mock",
        "attendees": guest_emails,
    }


def _build_credentials():
    sa_file = (settings.google_service_account_file or "").strip()
    if sa_file:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            sa_file,
            scopes=_SCOPES,
        )
        delegated = (settings.google_meet_delegated_user or "").strip()
        if delegated:
            creds = creds.with_subject(delegated)
        return creds

    client_id = (settings.google_oauth_client_id or "").strip()
    client_secret = (settings.google_oauth_client_secret or "").strip()
    refresh_token = (settings.google_oauth_refresh_token or "").strip()
    if client_id and client_secret and refresh_token:
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=list(_SCOPES),
        )

    raise ValueError(
        "GOOGLE_MEET_MODE=live requires either GOOGLE_SERVICE_ACCOUNT_FILE "
        "(+ optional GOOGLE_MEET_DELEGATED_USER) or "
        "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / "
        "GOOGLE_OAUTH_REFRESH_TOKEN"
    )


def _access_token() -> str:
    from google.auth.transport.requests import Request

    creds = _build_credentials()
    if not getattr(creds, "valid", False) or not getattr(creds, "token", None):
        creds.refresh(Request())
    token = getattr(creds, "token", None)
    if not token:
        raise ValueError("Failed to obtain Google access token for Meet API")
    return str(token)


def _create_live_meet(
    *,
    scheduled_at: datetime,
    duration_minutes: int,
    time_zone: str | None,
    attendees: list[str] | None = None,
) -> ScreeningMeetResult:
    guest_emails = list(dict.fromkeys(attendees or []))
    token = _access_token()
    payload = {
        "config": {
            "accessType": "OPEN",
            "entryPointAccess": "ALL",
        }
    }

    try:
        response = httpx.post(
            _MEET_SPACES_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "").strip()[:2000]
        raise ValueError(
            f"Google Meet API error: {exc.response.status_code} {body}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"Google Meet API unavailable: {exc}") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response from Google Meet API")

    meet_link = data.get("meetingUri")
    if not isinstance(meet_link, str) or not meet_link.strip():
        raise ValueError(
            "Google Meet space was created but no meetingUri was returned. "
            "Meet Spaces API usually requires a Google Workspace account."
        )

    return {
        "gmeet_link": meet_link.strip(),
        "meet_space_name": data.get("name") if isinstance(data.get("name"), str) else None,
        "meeting_code": (
            data.get("meetingCode") if isinstance(data.get("meetingCode"), str) else None
        ),
        "duration_minutes": duration_minutes,
        "time_zone": (time_zone or "UTC").strip() or "UTC",
        "scheduled_at": scheduled_at.isoformat(),
        "provider": "google_meet",
        "attendees": guest_emails,
    }


def create_screening_meet(
    *,
    scheduled_at: datetime,
    duration_minutes: int = 30,
    time_zone: str | None = None,
    attendees: list[str] | None = None,
) -> ScreeningMeetResult:
    """
    Generate a Google Meet join link (no Calendar event).

    mock → placeholder meet.google.com URL (local/dev)
    live → real space via Meet Spaces API
    """
    mode = _meet_mode()
    if mode not in {"mock", "live"}:
        raise ValueError("GOOGLE_MEET_MODE must be 'mock' or 'live'")
    if duration_minutes not in {30, 45, 60}:
        raise ValueError("duration_minutes must be 30, 45, or 60")

    if mode == "mock":
        return _create_mock_meet(
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            time_zone=time_zone,
            attendees=attendees,
        )

    return _create_live_meet(
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        time_zone=time_zone,
        attendees=attendees,
    )
