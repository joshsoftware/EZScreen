"""Track copying each screening's Attendee recording into MinIO.

ai-core does the actual copy (it talks to Attendee and MinIO); core-api owns
the state so it survives ai-core restarts. The state lives on
interview_session.interview_metadata["recording_import"]:

    {"status": "pending" | "in_progress" | "complete" | "failed",
     "bot_id": "...", "import_after": ISO-8601, "attempts": int,
     "claimed_at": ISO-8601 | None, "s3_key": str | None, "last_error": str | None}

Flow: schedule (bot ended) -> claim (due, marks in_progress) -> report result
(complete saves the key on interview_analysis.recording_url; failure retries
until recording_import_max_attempts, with exponential backoff).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.config.settings import settings
from src.models.application import Application
from src.models.enums import InterviewStatus
from src.models.interview_session import InterviewSession
from src.services.interview_analysis_service import _get_or_create_analysis
from src.services.storage_service import build_recording_s3_key, recording_key_prefix

__all__ = [
    "schedule_import",
    "claim_due_imports",
    "report_result",
    "recording_import_state",
    "get_session_for_import",
]

_NO_RECORDING_STATUSES = frozenset({InterviewStatus.failed, InterviewStatus.cancelled})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def recording_import_state(session: InterviewSession) -> dict[str, Any] | None:
    meta = session.interview_metadata if isinstance(session.interview_metadata, dict) else {}
    state = meta.get("recording_import")
    return state if isinstance(state, dict) else None


def _set_state(session: InterviewSession, state: dict[str, Any]) -> None:
    # Reassign a new dict so SQLAlchemy sees the JSONB change.
    meta = dict(session.interview_metadata or {})
    meta["recording_import"] = state
    session.interview_metadata = meta


def schedule_import(
    db: Session,
    session: InterviewSession,
    *,
    bot_id: str,
    import_after: datetime,
) -> dict[str, Any] | None:
    """Queue the copy. Idempotent: Attendee may redeliver the `ended` webhook."""
    if session.status in _NO_RECORDING_STATUSES:
        return None
    existing = recording_import_state(session)
    if existing and existing.get("status") in {"in_progress", "complete"}:
        return existing
    if import_after.tzinfo is None:
        import_after = import_after.replace(tzinfo=timezone.utc)
    state = {
        "status": "pending",
        "bot_id": bot_id,
        "import_after": import_after.isoformat(),
        "attempts": 0,
        "claimed_at": None,
        "s3_key": None,
        "last_error": None,
    }
    _set_state(session, state)
    db.add(session)
    db.commit()
    return state


def _is_due(state: dict[str, Any], now: datetime) -> bool:
    if state.get("status") == "pending":
        import_after = _parse(state.get("import_after"))
        return import_after is None or import_after <= now
    if state.get("status") == "in_progress":
        claimed_at = _parse(state.get("claimed_at"))
        stale_after = timedelta(seconds=settings.recording_import_stale_seconds)
        return claimed_at is None or now - claimed_at >= stale_after
    return False


def claim_due_imports(db: Session, *, limit: int) -> list[dict[str, Any]]:
    """Mark due imports in_progress and return what ai-core should copy."""
    now = _now()
    stmt = (
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.application).selectinload(
                Application.job_description
            )
        )
        .where(
            InterviewSession.interview_metadata["recording_import"]["status"].astext.in_(
                ["pending", "in_progress"]
            )
        )
        .order_by(InterviewSession.completed_at.asc().nullsfirst())
        .with_for_update(skip_locked=True, of=InterviewSession)
    )
    claimed: list[dict[str, Any]] = []
    for session in db.scalars(stmt):
        if len(claimed) >= limit:
            break
        state = recording_import_state(session)
        if not state or not _is_due(state, now):
            continue
        job = session.application.job_description if session.application else None
        if job is None:
            _set_state(
                session,
                {**state, "status": "failed", "last_error": "Job for session not found"},
            )
            db.add(session)
            continue
        s3_key = build_recording_s3_key(job.organization_id, job.id, session.id)
        attempt = int(state.get("attempts") or 0) + 1
        _set_state(
            session,
            {
                **state,
                "status": "in_progress",
                "claimed_at": now.isoformat(),
                "attempts": attempt,
                "s3_key": s3_key,
            },
        )
        db.add(session)
        claimed.append(
            {
                "interview_session_id": session.id,
                "bot_id": state.get("bot_id") or "",
                "s3_key": s3_key,
                "attempt": attempt,
            }
        )
    db.commit()
    return claimed


def retry_delay_seconds(attempts: int) -> int:
    """Backoff before the next try: 1 min, 2, 4, 8, ... capped at 1 hour."""
    delay = settings.recording_import_retry_seconds * 2 ** max(attempts - 1, 0)
    return min(delay, settings.recording_import_retry_max_seconds)


def report_result(
    db: Session,
    session: InterviewSession,
    *,
    success: bool,
    s3_key: str | None = None,
    error: str | None = None,
    retryable: bool = True,
) -> dict[str, Any]:
    state = recording_import_state(session)
    if state is None:
        raise LookupError("No recording import is scheduled for this session")

    if success:
        expected = state.get("s3_key")
        if not s3_key or s3_key != expected:
            raise ValueError("s3_key does not match the claimed recording key")
        job = session.application.job_description if session.application else None
        if job is None or not s3_key.startswith(
            recording_key_prefix(job.organization_id, job.id)
        ):
            raise ValueError("s3_key is outside this job's recordings folder")
        analysis = _get_or_create_analysis(db, session)
        analysis.recording_url = s3_key
        db.add(analysis)
        new_state = {**state, "status": "complete", "last_error": None}
    else:
        attempts = int(state.get("attempts") or 0)
        exhausted = attempts >= settings.recording_import_max_attempts
        if exhausted or not retryable:
            new_state = {**state, "status": "failed", "last_error": error}
        else:
            retry_at = _now() + timedelta(seconds=retry_delay_seconds(attempts))
            new_state = {
                **state,
                "status": "pending",
                "import_after": retry_at.isoformat(),
                "claimed_at": None,
                "last_error": error,
            }

    _set_state(session, new_state)
    db.add(session)
    db.commit()
    return new_state


def get_session_for_import(db: Session, session_id: UUID) -> InterviewSession | None:
    stmt = (
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.application).selectinload(
                Application.job_description
            ),
            selectinload(InterviewSession.analysis),
        )
        .where(InterviewSession.id == session_id)
    )
    return db.scalar(stmt)
