"""In-memory store for recent HR bulk resume ingest failures (per job)."""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

__all__ = [
    "record_ingest_error",
    "list_ingest_errors",
]

_LOCK = threading.Lock()
_MAX_ERRORS_PER_JOB = 100
_RETENTION = timedelta(hours=24)

# job_id -> deque of error dicts (newest last)
_ERRORS: dict[UUID, deque[dict[str, Any]]] = defaultdict(deque)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _prune_job_errors(job_id: UUID, *, now: datetime | None = None) -> None:
    bucket = _ERRORS.get(job_id)
    if not bucket:
        return
    cutoff = (now or _utcnow()) - _RETENTION
    while bucket and bucket[0]["created_at"] < cutoff:
        bucket.popleft()
    if not bucket:
        _ERRORS.pop(job_id, None)


def record_ingest_error(
    job_id: UUID,
    *,
    file_name: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    now = _utcnow()
    entry = {
        "id": str(uuid.uuid4()),
        "file_name": file_name,
        "error_code": error_code,
        "message": message,
        "created_at": now,
    }
    with _LOCK:
        bucket = _ERRORS[job_id]
        bucket.append(entry)
        while len(bucket) > _MAX_ERRORS_PER_JOB:
            bucket.popleft()
        _prune_job_errors(job_id, now=now)
    return entry


def list_ingest_errors(
    job_id: UUID,
    *,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    with _LOCK:
        _prune_job_errors(job_id)
        bucket = _ERRORS.get(job_id)
        if not bucket:
            return []
        items = list(bucket)
    if since is not None:
        items = [item for item in items if item["created_at"] >= since]
    return [
        {
            **item,
            "created_at": item["created_at"],
        }
        for item in items
    ]
