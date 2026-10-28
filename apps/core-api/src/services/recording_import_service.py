"""Track copying each screening's Attendee recording into MinIO.

ai-core does the actual copy (it talks to Attendee and MinIO); core-api owns
the state so it survives ai-core restarts. The state lives on
interview_session.interview_metadata["recording_import"]:

    {"status": "pending" | "in_progress" | "complete" | "failed",
     "bot_id": "...", "import_after": ISO-8601, "attempts": int,
     "claimed_at": ISO-8601 | None, "s3_key": str | None, "last_error": str | None}

A rescheduled session keeps each earlier attempt (and its own import state)
under interview_metadata["previous_attempts"]; those imports are claimed and
reported the same way, under that attempt's own recording key.

Flow: schedule (bot ended) -> claim (due, marks in_progress) -> report result
(complete saves the key on interview_analysis.recording_url, or on the earlier
attempt; failure retries until recording_import_max_attempts, with
exponential backoff).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, literal_column, or_, select
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
    "attempt_number",
    "previous_attempts",
]

_NO_RECORDING_STATUSES = frozenset({InterviewStatus.failed, InterviewStatus.cancelled})
_OPEN_IMPORT_STATUSES = ("pending", "in_progress")
# Sessions with an earlier attempt whose recording copy is still open.
_PREVIOUS_ATTEMPT_IMPORT_OPEN = literal_column(
    """'$.previous_attempts[*].recording_import.status ? (@ == "pending" || @ == "in_progress")'"""
)

# A slot is where one attempt's import state lives: None for the current
# attempt, else the index into previous_attempts.
_Slot = int | None


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


def _meta(session: InterviewSession) -> dict[str, Any]:
    return session.interview_metadata if isinstance(session.interview_metadata, dict) else {}


def attempt_number(meta: dict[str, Any]) -> int:
    """1 for the first booking; each reschedule after an attempt ran adds one."""
    value = meta.get("attempt_number")
    return value if isinstance(value, int) and value >= 1 else 1


def previous_attempts(meta: dict[str, Any]) -> list[dict[str, Any]]:
    raw = meta.get("previous_attempts")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def recording_import_state(session: InterviewSession) -> dict[str, Any] | None:
    state = _meta(session).get("recording_import")
    return state if isinstance(state, dict) else None


def _slot_state(session: InterviewSession, slot: _Slot) -> dict[str, Any] | None:
    if slot is None:
        return recording_import_state(session)
    attempts = previous_attempts(_meta(session))
    state = attempts[slot].get("recording_import") if slot < len(attempts) else None
    return state if isinstance(state, dict) else None


def _slots(session: InterviewSession) -> list[tuple[_Slot, dict[str, Any]]]:
    """Every attempt's import state: the current attempt first."""
    found: list[tuple[_Slot, dict[str, Any]]] = []
    current = recording_import_state(session)
    if current is not None:
        found.append((None, current))
    for index, attempt in enumerate(previous_attempts(_meta(session))):
        state = attempt.get("recording_import")
        if isinstance(state, dict):
            found.append((index, state))
    return found


def _set_state(session: InterviewSession, state: dict[str, Any], slot: _Slot = None) -> None:
    # Reassign new containers so SQLAlchemy sees the JSONB change.
    meta = dict(_meta(session))
    if slot is None:
        meta["recording_import"] = state
    else:
        attempts = [dict(item) for item in previous_attempts(meta)]
        attempts[slot]["recording_import"] = state
        meta["previous_attempts"] = attempts
    session.interview_metadata = meta


def new_import_state(*, bot_id: str, import_after: datetime) -> dict[str, Any]:
    if import_after.tzinfo is None:
        import_after = import_after.replace(tzinfo=timezone.utc)
    return {
        "status": "pending",
        "bot_id": bot_id,
        "import_after": import_after.isoformat(),
        "attempts": 0,
        "claimed_at": None,
        "s3_key": None,
        "last_error": None,
    }


def schedule_import(
    db: Session,
    session: InterviewSession,
    *,
    bot_id: str,
    import_after: datetime,
) -> dict[str, Any] | None:
    """Queue the copy. Idempotent: Attendee may redeliver the `ended` webhook."""
    slot: _Slot = None
    for index, attempt in enumerate(previous_attempts(_meta(session))):
        if attempt.get("bot_id") == bot_id:
            # The bot of an attempt that was rescheduled since.
            slot = index
            break
    if slot is None and session.status in _NO_RECORDING_STATUSES:
        return None
    existing = _slot_state(session, slot)
    if existing and existing.get("status") in {"in_progress", "complete"}:
        return existing
    state = new_import_state(bot_id=bot_id, import_after=import_after)
    _set_state(session, state, slot)
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


def _slot_s3_key(session: InterviewSession, slot: _Slot, job) -> str:
    meta = _meta(session)
    if slot is None:
        number = attempt_number(meta)
    else:
        number = previous_attempts(meta)[slot].get("attempt")
        number = number if isinstance(number, int) else 1
    return build_recording_s3_key(job.organization_id, job.id, session.id, attempt=number)


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
            or_(
                InterviewSession.interview_metadata["recording_import"]["status"].astext.in_(
                    _OPEN_IMPORT_STATUSES
                ),
                func.jsonb_path_exists(
                    InterviewSession.interview_metadata, _PREVIOUS_ATTEMPT_IMPORT_OPEN
                ),
            )
        )
        .order_by(InterviewSession.completed_at.asc().nullsfirst())
        .with_for_update(skip_locked=True, of=InterviewSession)
    )
    claimed: list[dict[str, Any]] = []
    for session in db.scalars(stmt):
        job = session.application.job_description if session.application else None
        for slot, state in _slots(session):
            if len(claimed) >= limit:
                break
            if not _is_due(state, now):
                continue
            if job is None:
                _set_state(
                    session,
                    {**state, "status": "failed", "last_error": "Job for session not found"},
                    slot,
                )
                db.add(session)
                continue
            s3_key = _slot_s3_key(session, slot, job)
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
                slot,
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
        if len(claimed) >= limit:
            break
    db.commit()
    return claimed


def retry_delay_seconds(attempts: int) -> int:
    """Backoff before the next try: 1 min, 2, 4, 8, ... capped at 1 hour."""
    delay = settings.recording_import_retry_seconds * 2 ** max(attempts - 1, 0)
    return min(delay, settings.recording_import_retry_max_seconds)


def _find_reported_slot(
    session: InterviewSession, s3_key: str | None
) -> tuple[_Slot, dict[str, Any]] | None:
    slots = _slots(session)
    if s3_key:
        for slot, state in slots:
            if state.get("s3_key") == s3_key:
                return slot, state
    # Without a key (older ai-core failure reports): the copy being worked on.
    for slot, state in slots:
        if state.get("status") == "in_progress":
            return slot, state
    return slots[0] if slots else None


def report_result(
    db: Session,
    session: InterviewSession,
    *,
    success: bool,
    s3_key: str | None = None,
    error: str | None = None,
    retryable: bool = True,
) -> dict[str, Any]:
    found = _find_reported_slot(session, s3_key)
    if found is None:
        raise LookupError("No recording import is scheduled for this session")
    slot, state = found

    if success:
        expected = state.get("s3_key")
        if not s3_key or s3_key != expected:
            raise ValueError("s3_key does not match the claimed recording key")
        job = session.application.job_description if session.application else None
        if job is None or not s3_key.startswith(
            recording_key_prefix(job.organization_id, job.id)
        ):
            raise ValueError("s3_key is outside this job's recordings folder")
        if slot is None:
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

    _set_state(session, new_state, slot)
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
