"""Google Calendar events with Meet links for AI screening interviews."""

from __future__ import annotations

import logging
import secrets
import socket
import string
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, TypedDict
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

__all__ = [
    "ScreeningMeetResult",
    "create_screening_meet",
]

_SCOPES = ("https://www.googleapis.com/auth/calendar.events",)
_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_MEET_CODE_ALPHABET = string.ascii_lowercase

# Browser/OS legacy names not always present in Python tzdata.
_TIMEZONE_ALIASES: dict[str, str] = {
    "Asia/Calcutta": "Asia/Kolkata",
}


@contextmanager
def _prefer_ipv4() -> Iterator[None]:
    """Prefer IPv4 for outbound calls (Docker often has no IPv6 route → Errno 101)."""
    import urllib3.util.connection as urllib3_cn

    previous = urllib3_cn.allowed_gai_family
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
    try:
        yield
    finally:
        urllib3_cn.allowed_gai_family = previous


def _google_http_client(*, timeout: float = 30.0) -> httpx.Client:
    # Bind to IPv4 so httpx does not try unreachable AAAA addresses.
    return httpx.Client(
        timeout=timeout,
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
    )


class ScreeningMeetResult(TypedDict, total=False):
    gmeet_link: str
    meet_space_name: str | None
    meeting_code: str | None
    duration_minutes: int
    time_zone: str | None
    scheduled_at: str
    provider: str
    attendees: list[str]
    calendar_event_id: str | None
    calendar_html_link: str | None


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
        "calendar_event_id": None,
        "calendar_html_link": None,
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
        if not delegated:
            raise ValueError(
                "GOOGLE_MEET_DELEGATED_USER is required when using "
                "GOOGLE_SERVICE_ACCOUNT_FILE with Google Calendar"
            )
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
        "+ GOOGLE_MEET_DELEGATED_USER or "
        "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / "
        "GOOGLE_OAUTH_REFRESH_TOKEN"
    )


def _access_token() -> str:
    from google.auth.transport.requests import Request

    creds = _build_credentials()
    if not getattr(creds, "valid", False) or not getattr(creds, "token", None):
        with _prefer_ipv4():
            creds.refresh(Request())
    token = getattr(creds, "token", None)
    if not token:
        raise ValueError("Failed to obtain Google access token for Calendar API")
    return str(token)


def _resolve_timezone_name(time_zone: str | None) -> str:
    cleaned = (time_zone or "UTC").strip() or "UTC"
    cleaned = _TIMEZONE_ALIASES.get(cleaned, cleaned)
    try:
        ZoneInfo(cleaned)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid time_zone: {cleaned}") from exc
    return cleaned


def _local_event_bounds(
    *,
    scheduled_at: datetime,
    duration_minutes: int,
    time_zone: str,
) -> tuple[str, str]:
    start = scheduled_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    local_start = start.astimezone(ZoneInfo(time_zone))
    local_end = local_start + timedelta(minutes=duration_minutes)
    fmt = "%Y-%m-%dT%H:%M:%S"
    return local_start.strftime(fmt), local_end.strftime(fmt)


def _extract_meet_link(event: dict[str, Any]) -> str | None:
    hangout = event.get("hangoutLink")
    if isinstance(hangout, str) and hangout.strip():
        return hangout.strip()

    conference = event.get("conferenceData")
    if isinstance(conference, dict):
        entry_points = conference.get("entryPoints")
        if isinstance(entry_points, list):
            for entry in entry_points:
                if not isinstance(entry, dict):
                    continue
                if entry.get("entryPointType") == "video":
                    uri = entry.get("uri")
                    if isinstance(uri, str) and uri.strip():
                        return uri.strip()
    return None


def _extract_meeting_code(meet_link: str) -> str | None:
    prefix = "https://meet.google.com/"
    if meet_link.startswith(prefix):
        code = meet_link[len(prefix) :].strip("/")
        return code or None
    return None


def _calendar_events_url(calendar_id: str) -> str:
    encoded = quote(calendar_id, safe="")
    return _CALENDAR_EVENTS_URL.format(calendar_id=encoded)


def _create_live_calendar_event(
    *,
    scheduled_at: datetime,
    duration_minutes: int,
    time_zone: str | None,
    attendees: list[str] | None = None,
    event_summary: str | None = None,
    event_description: str | None = None,
) -> ScreeningMeetResult:
    guest_emails = list(dict.fromkeys(attendees or []))
    tz_name = _resolve_timezone_name(time_zone)
    start_str, end_str = _local_event_bounds(
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        time_zone=tz_name,
    )

    calendar_id = (settings.google_calendar_id or "primary").strip() or "primary"
    send_updates = (settings.google_calendar_send_updates or "all").strip() or "all"
    if send_updates not in {"all", "externalOnly", "none"}:
        raise ValueError(
            "GOOGLE_CALENDAR_SEND_UPDATES must be one of: all, externalOnly, none"
        )

    payload: dict[str, Any] = {
        "summary": (event_summary or "EZScreen AI Screening").strip(),
        "description": (event_description or "").strip(),
        "start": {"dateTime": start_str, "timeZone": tz_name},
        "end": {"dateTime": end_str, "timeZone": tz_name},
        "attendees": [{"email": email} for email in guest_emails],
        "conferenceData": {
            "createRequest": {
                "requestId": f"ezscreen-{uuid4()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {"useDefault": True},
    }

    token = _access_token()
    url = _calendar_events_url(calendar_id)
    params = {"conferenceDataVersion": "1", "sendUpdates": send_updates}

    try:
        with _google_http_client(timeout=30.0) as client:
            response = client.post(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "").strip()[:2000]
        raise ValueError(
            f"Google Calendar API error: {exc.response.status_code} {body}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"Google Calendar API unavailable: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid response from Google Calendar API")

    meet_link = _extract_meet_link(data)
    if not meet_link:
        raise ValueError(
            "Calendar event was created but no Google Meet link was returned. "
            "Ensure the organizer account has Google Meet enabled (Workspace)."
        )

    event_id = data.get("id") if isinstance(data.get("id"), str) else None
    html_link = data.get("htmlLink") if isinstance(data.get("htmlLink"), str) else None

    logger.info(
        "Created Google Calendar screening event id=%s meet=%s attendees=%s",
        event_id,
        meet_link,
        guest_emails,
    )

    return {
        "gmeet_link": meet_link,
        "meet_space_name": event_id,
        "meeting_code": _extract_meeting_code(meet_link),
        "duration_minutes": duration_minutes,
        "time_zone": tz_name,
        "scheduled_at": scheduled_at.isoformat(),
        "provider": "google_calendar",
        "attendees": guest_emails,
        "calendar_event_id": event_id,
        "calendar_html_link": html_link,
    }


def create_screening_meet(
    *,
    scheduled_at: datetime,
    duration_minutes: int = 30,
    time_zone: str | None = None,
    attendees: list[str] | None = None,
    event_summary: str | None = None,
    event_description: str | None = None,
) -> ScreeningMeetResult:
    """
    Schedule screening via Google Calendar (live) or placeholder link (mock).

    mock → placeholder meet.google.com URL (local/dev)
    live → Calendar event with auto-generated Meet link + attendee invites
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

    return _create_live_calendar_event(
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        time_zone=time_zone,
        attendees=attendees,
        event_summary=event_summary,
        event_description=event_description,
    )
