"""Copy each screening's Attendee meeting recording (MP4) into MinIO.

Attendee only offers a short-lived download URL, so EZScreen keeps its own
copy for HR to replay. core-api owns the import state (it survives ai-core
restarts); this module does the work:

1. On the bot's `ended` webhook, ask core-api to schedule the copy
   RECORDING_SAVE_DELAY_SECONDS later (Attendee needs time to finish the file).
2. A poller started with the app claims due imports from core-api every
   RECORDING_IMPORT_POLL_SECONDS.
3. For each: fetch the recording URL from Attendee, stream the MP4 into the
   recordings bucket under the key core-api chose, and report the result.

Transcripts and scoring never wait on this, and a failed copy never changes
the session's own status.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from src.core.config import settings
from src.core.logger import logger
from src.core.storage import storage_client
from src.meeting_bot.attendee import attendee_client

_CLAIM_LIMIT = 3


class RecordingNotReady(Exception):
    """Attendee has no downloadable recording yet."""


def _core_api(path: str) -> str:
    return f"{settings.core_api_url.rstrip('/')}/api/v1/interview-sessions{path}"


def _headers() -> dict[str, str]:
    if settings.internal_service_token:
        return {"X-Internal-Service-Token": settings.internal_service_token}
    return {}


async def schedule_recording_import(session_id: str, bot_id: str) -> None:
    """Called when the bot reaches `ended`. Never raises."""
    import_after = datetime.now(timezone.utc) + timedelta(
        seconds=settings.recording_save_delay_seconds
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _core_api(f"/{session_id}/recording-import"),
                json={"bot_id": bot_id, "import_after": import_after.isoformat()},
                headers=_headers(),
            )
            resp.raise_for_status()
        logger.info(
            "Scheduled meeting recording copy",
            extra={"session_id": session_id, "bot_id": bot_id, "import_after": import_after.isoformat()},
        )
    except Exception as err:
        logger.error(
            "Failed to schedule meeting recording copy",
            extra={"session_id": session_id, "bot_id": bot_id, "error": str(err)},
        )


def _copy_to_minio(url: str, s3_key: str) -> None:
    """Blocking: stream Attendee's MP4 straight into MinIO."""
    timeout = httpx.Timeout(30.0, read=300.0)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
        if resp.status_code == 404:
            raise RecordingNotReady("Recording file not available yet")
        resp.raise_for_status()
        storage_client.upload_stream(
            resp.iter_bytes(chunk_size=1024 * 1024),
            s3_key,
            bucket_name=settings.minio_bucket_recordings,
            content_type="video/mp4",
        )


async def _report(session_id: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _core_api(f"/{session_id}/recording-import/result"),
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()


async def import_recording(session_id: str, bot_id: str, s3_key: str) -> None:
    """Copy one recording and report the outcome to core-api. Never raises."""
    try:
        url = await attendee_client.get_recording_url(bot_id)
        if not url:
            raise RecordingNotReady("Attendee has no recording URL yet")
        await asyncio.to_thread(_copy_to_minio, url, s3_key)
    except Exception as err:
        logger.warning(
            "Meeting recording copy failed",
            extra={"session_id": session_id, "bot_id": bot_id, "error": str(err)},
        )
        # s3_key tells core-api which attempt of a rescheduled session failed.
        payload = {"success": False, "s3_key": s3_key, "error": str(err)[:1000], "retryable": True}
    else:
        logger.info(
            "Meeting recording saved to MinIO",
            extra={"session_id": session_id, "s3_key": s3_key},
        )
        payload = {"success": True, "s3_key": s3_key}
    try:
        await _report(session_id, payload)
    except Exception as err:
        # core-api will hand the import out again once it goes stale.
        logger.error(
            "Failed to report meeting recording copy result",
            extra={"session_id": session_id, "error": str(err)},
        )


async def _claim_due() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _core_api("/recording-imports/claim"),
            json={"limit": _CLAIM_LIMIT},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("imports", [])


async def run_recording_import_poller() -> None:
    """Background loop started from the app lifespan."""
    while True:
        try:
            for item in await _claim_due():
                await import_recording(
                    str(item["interview_session_id"]), item["bot_id"], item["s3_key"]
                )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            logger.warning("Recording import poll failed", extra={"error": str(err)})
        await asyncio.sleep(settings.recording_import_poll_seconds)
