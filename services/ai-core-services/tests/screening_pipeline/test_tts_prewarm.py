import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

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
from src.screening_pipeline.tts_prewarm import (
    TtsPrewarmRegistry,
    coerce_questions_list,
    known_bot_texts,
)


def test_coerce_questions_list_accepts_list_and_nested_dict_shapes():
    assert coerce_questions_list([{"question": "Q1"}, {"no_question": True}]) == [
        {"question": "Q1"}
    ]
    assert coerce_questions_list({"questions": [{"question": "Q2"}]}) == [
        {"question": "Q2"}
    ]
    assert coerce_questions_list(None) == []
    assert coerce_questions_list("garbage") == []


def test_known_bot_texts_includes_constants_and_question_text():
    texts = known_bot_texts([{"question": "What is Docker?"}, {"question": ""}])

    assert texts == [
        GREETING_TEXT,
        CLOSING_TEXT,
        SILENCE_PROMPT_TEXT,
        ANSWER_ACKNOWLEDGEMENT_TEXT,
        REPEAT_QUESTION_PREFIX_TEXT,
        REPEAT_QUESTION_LIMIT_TEXT,
        *FILLER_TEXTS,
        "What is Docker?",
    ]


def test_compute_delay_targets_lead_seconds_before_join():
    join_at = datetime.now(timezone.utc) + timedelta(seconds=500)

    delay = TtsPrewarmRegistry._compute_delay(join_at, lead_seconds=120)

    assert 375 <= delay <= 385  # ~500 - 120, allowing for test execution time


def test_compute_delay_is_zero_when_join_is_within_the_lead_window():
    join_at = datetime.now(timezone.utc) + timedelta(seconds=30)

    assert TtsPrewarmRegistry._compute_delay(join_at, lead_seconds=120) == 0.0


def test_compute_delay_is_zero_when_join_at_is_unknown():
    assert TtsPrewarmRegistry._compute_delay(None, lead_seconds=120) == 0.0


@pytest.mark.asyncio
async def test_schedule_warms_and_claim_returns_the_finished_synthesizer():
    registry = TtsPrewarmRegistry(lead_seconds=0, ttl_seconds=3600, max_concurrent=3)
    warm_calls: list[list[str]] = []

    async def fake_warm(self, texts):
        warm_calls.append(list(texts))
        self._cache["fake"] = [b"pcm"]

    with patch.object(KokoroSynthesizer, "warm", fake_warm):
        registry.schedule(
            "session-1", [{"question": "What is Docker?"}], join_at=None
        )
        await asyncio.sleep(0)  # let the scheduled task run

    claimed = registry.claim("session-1")

    assert claimed is not None
    assert claimed._cache == {"fake": [b"pcm"]}
    assert warm_calls == [
        [
            GREETING_TEXT,
            CLOSING_TEXT,
            SILENCE_PROMPT_TEXT,
            ANSWER_ACKNOWLEDGEMENT_TEXT,
            REPEAT_QUESTION_PREFIX_TEXT,
            REPEAT_QUESTION_LIMIT_TEXT,
            *FILLER_TEXTS,
            "What is Docker?",
        ]
    ]
    # Claimed once; a second claim for the same session is a miss.
    assert registry.claim("session-1") is None


def test_claim_without_a_schedule_is_a_miss():
    registry = TtsPrewarmRegistry()

    assert registry.claim("never-scheduled") is None


@pytest.mark.asyncio
async def test_claim_after_ttl_expiry_is_a_miss():
    registry = TtsPrewarmRegistry(lead_seconds=0, ttl_seconds=0, max_concurrent=3)

    async def fake_warm(self, texts):
        self._cache["fake"] = [b"pcm"]

    with patch.object(KokoroSynthesizer, "warm", fake_warm):
        registry.schedule("session-1", [], join_at=None)
        await asyncio.sleep(0)

    # ttl_seconds=0 means any elapsed monotonic time already expires it.
    assert registry.claim("session-1") is None


@pytest.mark.asyncio
async def test_a_prewarm_failure_leaves_no_entry_and_does_not_raise():
    registry = TtsPrewarmRegistry(lead_seconds=0, ttl_seconds=3600, max_concurrent=3)

    async def failing_warm(self, texts):
        raise RuntimeError("kokoro exploded")

    with patch.object(KokoroSynthesizer, "warm", failing_warm):
        registry.schedule("session-1", [], join_at=None)
        await asyncio.sleep(0)

    assert registry.claim("session-1") is None


@pytest.mark.asyncio
async def test_concurrent_prewarms_are_bounded_by_max_concurrent():
    registry = TtsPrewarmRegistry(lead_seconds=0, ttl_seconds=3600, max_concurrent=2)
    active = 0
    max_active_seen = 0
    release = asyncio.Event()

    async def slow_warm(self, texts):
        nonlocal active, max_active_seen
        active += 1
        max_active_seen = max(max_active_seen, active)
        await release.wait()
        active -= 1

    with patch.object(KokoroSynthesizer, "warm", slow_warm):
        for i in range(4):
            registry.schedule(f"session-{i}", [], join_at=None)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert max_active_seen == 2  # bounded, not all 4 running at once

        release.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    for i in range(4):
        assert registry.claim(f"session-{i}") is not None
