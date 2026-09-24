"""Schedules TTS warm-up ahead of an interview's scheduled join time.

Phase 4 (see docs/architecture/SCREENING_BOT_LATENCY_OPTIMIZATION.md §7) already warms the
per-session Kokoro cache as soon as the Pipecat WebSocket session starts — i.e. after the bot
has joined the meeting and Attendee has connected back to us. That means ~1–1.5 minutes of
CPU-bound synthesis for a full question set lands in the same narrow window as the greeting and
the candidate's first turn, competing for CPU with real-time VAD/STT work.

This module moves that work earlier: dispatch_bot() schedules a background job timed to finish
shortly before the bot's scheduled join time, so the cache is already warm before the live
session even starts. It intentionally does NOT introduce a global/shared Kokoro instance — each
interview still gets its own KokoroSynthesizer and its own cache, exactly as before; only the
*timing* of when that object is created and warmed moves earlier. The finished synthesizer is
handed off to the later PipecatInterviewRuntime through this in-process registry.

In-process only: this service runs as a single Uvicorn process/container today (see
docker-compose.yml — no --workers flag, no replicas). If that ever changes to multiple workers
or replicas, this handoff would need a shared store (e.g. Redis) instead, since a pre-warm job
and the WebSocket session it's for could then land on different processes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from src.core.logger import logger
from src.screening_pipeline.pipecat_tts import KokoroSynthesizer
from src.screening_pipeline.prompts import (
    ANSWER_ACKNOWLEDGEMENT_TEXT,
    CLOSING_TEXT,
    FILLER_TEXTS,
    GREETING_TEXT,
    REPEAT_QUESTION_LIMIT_TEXT,
    REPEAT_QUESTION_PREFIX_TEXT,
    SILENCE_PROMPT_TEXT,
)

# Finish warming this long before the bot is scheduled to join.
PREWARM_LEAD_SECONDS = 120
# Drop an unclaimed pre-warm (bot never joined / interview cancelled after
# dispatch) instead of holding its loaded model in memory indefinitely. Kept
# comfortably above PREWARM_LEAD_SECONDS so a late-joining bot (Attendee
# delays, retries, etc.) still finds its cache warm.
PREWARM_ENTRY_TTL_SECONDS = 30 * 60
# Bound how many pre-warm jobs run their actual synthesis at once, so a
# cluster of interviews scheduled close together doesn't spike CPU all at
# the same moment. Live (already-joined) sessions are never throttled by
# this — only background pre-warming is.
MAX_CONCURRENT_PREWARMS = 3


def coerce_questions_list(raw: Any) -> list[dict]:
    """Normalize session.generated_questions to a list of question dicts."""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        nested = raw.get("questions")
        items = nested if isinstance(nested, list) else []
    else:
        items = []
    return [item for item in items if isinstance(item, dict) and item.get("question")]


def known_bot_texts(questions: list[dict]) -> list[str]:
    """Every deterministic string PipecatInterviewPolicy will speak for this session."""
    texts = [
        GREETING_TEXT,
        CLOSING_TEXT,
        SILENCE_PROMPT_TEXT,
        ANSWER_ACKNOWLEDGEMENT_TEXT,
        REPEAT_QUESTION_PREFIX_TEXT,
        REPEAT_QUESTION_LIMIT_TEXT,
    ]
    texts.extend(FILLER_TEXTS)
    texts.extend(q.get("question", "") for q in questions if q.get("question"))
    return texts


class _PrewarmEntry:
    __slots__ = ("synthesizer", "created_at")

    def __init__(self, synthesizer: KokoroSynthesizer):
        self.synthesizer = synthesizer
        self.created_at = time.monotonic()


class TtsPrewarmRegistry:
    """In-process handoff from a scheduled pre-warm job to the live session it's for."""

    def __init__(
        self,
        *,
        lead_seconds: float = PREWARM_LEAD_SECONDS,
        ttl_seconds: float = PREWARM_ENTRY_TTL_SECONDS,
        max_concurrent: int = MAX_CONCURRENT_PREWARMS,
    ):
        self._lead_seconds = lead_seconds
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, _PrewarmEntry] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            session_id
            for session_id, entry in self._entries.items()
            if now - entry.created_at > self._ttl_seconds
        ]
        for session_id in expired:
            self._entries.pop(session_id, None)

    def claim(self, session_id: str) -> KokoroSynthesizer | None:
        """Pop the pre-warmed synthesizer for this session, if one finished in time.

        Returns None on a miss (too early, pre-warm still running, it expired,
        or none was scheduled) — the caller falls back to building a fresh
        KokoroSynthesizer and warming it at session start, same as before this
        module existed.
        """
        self._evict_expired()
        entry = self._entries.pop(session_id, None)
        return entry.synthesizer if entry else None

    def schedule(
        self,
        session_id: str,
        questions: list[dict],
        *,
        join_at: datetime | None,
    ) -> None:
        """Fire a background pre-warm job timed to finish shortly before join_at.

        Never awaited by the caller (dispatch_bot must not block on this) and
        never raises: any failure is logged and simply leaves nothing in the
        registry, so the session-start warm-up covers it instead.
        """
        texts = known_bot_texts(questions)
        if not texts:
            return
        delay = self._compute_delay(join_at, self._lead_seconds)
        asyncio.create_task(self._run_after_delay(session_id, texts, delay))

    @staticmethod
    def _compute_delay(join_at: datetime | None, lead_seconds: float) -> float:
        """Seconds to wait before starting synthesis, so it finishes ~lead_seconds
        before join_at. 0 (start immediately) when join_at is unknown or already
        within the lead window."""
        if join_at is None:
            return 0.0
        seconds_until_join = (join_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, seconds_until_join - lead_seconds)

    async def _run_after_delay(self, session_id: str, texts: list[str], delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        async with self._semaphore:
            logger.info(
                "TTS pre-warm started",
                extra={"session_id": session_id, "texts": len(texts)},
            )
            started_at = time.monotonic()
            synthesizer = KokoroSynthesizer()
            try:
                await synthesizer.warm(texts)
            except Exception as err:
                logger.error(
                    "TTS pre-warm failed; live session will warm on demand instead",
                    extra={"session_id": session_id, "error": str(err)},
                )
                return
        self._evict_expired()
        self._entries[session_id] = _PrewarmEntry(synthesizer)
        logger.info(
            "TTS pre-warm finished ahead of bot join",
            extra={
                "session_id": session_id,
                "texts": len(texts),
                "duration_seconds": round(time.monotonic() - started_at, 2),
            },
        )


tts_prewarm_registry = TtsPrewarmRegistry()
