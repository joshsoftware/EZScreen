"""Dispatch Attendee meeting bots via ai-core-services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from src.config.settings import settings

__all__ = ["abort_screening_session", "dispatch_screening_bot"]


def _dispatch_url() -> str:
    return f"{settings.ai_services_base_url.rstrip('/')}/screening/bot/dispatch"


def abort_screening_session(*, interview_session_id: UUID, bot_id: str | None) -> str | None:
    """Stop a live interview without saving it and pull its bot out.

    Returns None on success, else an error message.
    """
    url = f"{settings.ai_services_base_url.rstrip('/')}/screening/bot/abort"
    body: dict[str, str] = {"interview_session_id": str(interview_session_id)}
    if bot_id:
        body["bot_id"] = bot_id
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return f"Could not stop the current interview: {exc}"
    if isinstance(data, dict) and data.get("status") == "error":
        return str(data.get("error_message") or "Could not stop the current interview")
    return None


def dispatch_screening_bot(
    *,
    interview_session_id: UUID,
    meeting_url: str | None = None,
) -> dict[str, Any]:
    """
    Schedule an Attendee bot for an interview session.

    Returns a normalized payload for interview_metadata (always includes status).
    """
    body: dict[str, str] = {"interview_session_id": str(interview_session_id)}
    if meeting_url:
        body["meeting_url"] = meeting_url

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(_dispatch_url(), json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        detail = str(exc)
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            try:
                payload = exc.response.json()
                if isinstance(payload, dict) and payload.get("detail"):
                    detail = str(payload["detail"])
            except ValueError:
                detail = exc.response.text[:200] or detail
        return {
            "status": "error",
            "error_message": f"Bot dispatch failed: {detail}",
        }

    data = response.json()
    if not isinstance(data, dict):
        return {
            "status": "error",
            "error_message": "Bot dispatch returned an invalid response",
        }

    bot_id = data.get("bot_id")
    if not isinstance(bot_id, str) or not bot_id.strip():
        return {
            "status": "error",
            "error_message": "Bot dispatch response missing bot_id",
        }

    return {
        "status": "success",
        "bot_id": bot_id,
        "bot_status": str(data.get("status") or "scheduled"),
        "meeting_url": data.get("meeting_url"),
        "scheduled_at": data.get("scheduled_at"),
        "dispatched_at": data.get("dispatched_at"),
    }
