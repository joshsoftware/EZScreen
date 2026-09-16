"""In-memory progress + SSE fan-out for HR bulk resume ingest batches."""

from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

__all__ = [
    "start_batch",
    "mark_item_success",
    "mark_item_failure",
    "subscribe",
    "unsubscribe",
    "get_batch_snapshot",
]


@dataclass
class _Batch:
    batch_id: str
    job_id: UUID
    queued: int
    completed: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    subscribers: list[queue.Queue] = field(default_factory=list)
    done: bool = False


_LOCK = threading.Lock()
_BATCHES: dict[str, _Batch] = {}
_LATEST_BY_JOB: dict[UUID, str] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_error(entry: dict[str, Any]) -> dict[str, Any]:
    created = entry.get("created_at")
    if isinstance(created, datetime):
        created_at = created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        created_at = created or _utcnow_iso()
    return {
        "id": str(entry.get("id") or uuid4()),
        "file_name": entry.get("file_name") or "",
        "error_code": entry.get("error_code") or "processing_failed",
        "message": entry.get("message") or "Resume processing failed",
        "created_at": created_at,
    }


def _snapshot(batch: _Batch, *, event: str = "snapshot", **extra: Any) -> dict[str, Any]:
    finished = batch.completed + batch.failed
    remaining = max(0, batch.queued - finished)
    done = batch.done or remaining == 0
    payload = {
        "event": event,
        "batch_id": batch.batch_id,
        "job_id": str(batch.job_id),
        "queued": batch.queued,
        "completed": batch.completed,
        "failed": batch.failed,
        "remaining": remaining,
        "done": done,
        "errors": [_serialize_error(item) for item in batch.errors],
        "ts": _utcnow_iso(),
    }
    payload.update(extra)
    return payload


def _publish(batch: _Batch, payload: dict[str, Any]) -> None:
    dead: list[queue.Queue] = []
    for subscriber in batch.subscribers:
        try:
            subscriber.put_nowait(payload)
        except queue.Full:
            try:
                subscriber.get_nowait()
            except queue.Empty:
                pass
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                dead.append(subscriber)
    if dead:
        batch.subscribers = [item for item in batch.subscribers if item not in dead]


def start_batch(job_id: UUID, queued: int) -> str:
    batch_id = str(uuid4())
    batch = _Batch(batch_id=batch_id, job_id=job_id, queued=max(0, int(queued)))
    if batch.queued == 0:
        batch.done = True
    with _LOCK:
        _BATCHES[batch_id] = batch
        _LATEST_BY_JOB[job_id] = batch_id
    return batch_id


def mark_item_success(batch_id: str, *, file_name: str) -> dict[str, Any] | None:
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if batch is None:
            return None
        batch.completed += 1
        if batch.completed + batch.failed >= batch.queued:
            batch.done = True
        payload = _snapshot(
            batch,
            event="item",
            file_name=file_name,
            item_status="success",
        )
        _publish(batch, payload)
        return payload


def mark_item_failure(
    batch_id: str,
    *,
    error: dict[str, Any],
) -> dict[str, Any] | None:
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if batch is None:
            return None
        batch.failed += 1
        batch.errors.append(error)
        if batch.completed + batch.failed >= batch.queued:
            batch.done = True
        payload = _snapshot(
            batch,
            event="item",
            file_name=error.get("file_name") or "",
            item_status="failed",
        )
        _publish(batch, payload)
        return payload


def get_batch_snapshot(batch_id: str) -> dict[str, Any] | None:
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if batch is None:
            return None
        return _snapshot(batch)


def subscribe(batch_id: str) -> tuple[queue.Queue, dict[str, Any]] | None:
    subscriber: queue.Queue = queue.Queue(maxsize=64)
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if batch is None:
            return None
        snapshot = _snapshot(batch)
        batch.subscribers.append(subscriber)
    subscriber.put_nowait(snapshot)
    return subscriber, snapshot


def unsubscribe(batch_id: str, subscriber: queue.Queue) -> None:
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if batch is None:
            return
        batch.subscribers = [item for item in batch.subscribers if item is not subscriber]


def encode_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"
