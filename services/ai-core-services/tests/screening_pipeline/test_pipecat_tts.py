import asyncio

import numpy as np
import pytest

from src.screening_pipeline.pipecat_tts import KokoroSynthesizer, KokoroTTSService

_BATCH = np.array([0.0, 0.1, -0.1, 0.2], dtype=np.float32)


def _make_synthesizer_with_fake_model(
    create_calls: list[str], *, batches_per_text: int = 1
) -> KokoroSynthesizer:
    synthesizer = KokoroSynthesizer(model_path="unused", voices_path="unused")

    async def _ensure_ready() -> None:
        return None

    async def _create_stream(text: str, voice: str, speed: float, lang: str):
        create_calls.append(text)
        for _ in range(batches_per_text):
            yield _BATCH, 24000

    synthesizer.ensure_ready = _ensure_ready  # type: ignore[method-assign]
    synthesizer.kokoro = type(
        "FakeKokoro", (), {"create_stream": staticmethod(_create_stream)}
    )()
    return synthesizer


@pytest.mark.asyncio
async def test_synthesize_caches_pcm_and_skips_model_on_repeat():
    create_calls: list[str] = []
    synthesizer = _make_synthesizer_with_fake_model(create_calls)

    first = [chunk async for chunk in synthesizer.synthesize("Hello there")]
    second = [chunk async for chunk in synthesizer.synthesize("Hello there")]

    assert create_calls == ["Hello there"]
    assert first == second
    assert "Hello there" in synthesizer._cache


@pytest.mark.asyncio
async def test_warm_populates_cache_for_all_known_texts_without_duplicates():
    create_calls: list[str] = []
    synthesizer = _make_synthesizer_with_fake_model(create_calls)

    await synthesizer.warm(["Q1", "Q2", "Q1", "", "Q2"])

    assert create_calls == ["Q1", "Q2"]
    assert set(synthesizer._cache) == {"Q1", "Q2"}

    # A later live speak() call for a warmed string must not re-synthesize.
    [chunk async for chunk in synthesizer.synthesize("Q1")]
    assert create_calls == ["Q1", "Q2"]


@pytest.mark.asyncio
async def test_warm_skips_texts_already_cached():
    create_calls: list[str] = []
    synthesizer = _make_synthesizer_with_fake_model(create_calls)

    [chunk async for chunk in synthesizer.synthesize("Greeting")]
    await synthesizer.warm(["Greeting", "Closing"])

    assert create_calls == ["Greeting", "Closing"]


@pytest.mark.asyncio
async def test_concurrent_synthesize_calls_for_same_text_only_invoke_model_once():
    create_calls: list[str] = []
    synthesizer = _make_synthesizer_with_fake_model(create_calls)

    async def drain():
        return [chunk async for chunk in synthesizer.synthesize("Racing text")]

    results = await asyncio.gather(drain(), drain())

    assert create_calls == ["Racing text"]
    assert results[0] == results[1]


@pytest.mark.asyncio
async def test_kokoro_tts_service_warm_cache_delegates_to_synthesizer():
    create_calls: list[str] = []
    synthesizer = _make_synthesizer_with_fake_model(create_calls)
    service = KokoroTTSService(synthesizer=synthesizer)

    await service.warm_cache(["Warm me"])

    assert create_calls == ["Warm me"]
    assert "Warm me" in synthesizer._cache


@pytest.mark.asyncio
async def test_cache_miss_yields_audio_per_sentence_batch_not_the_whole_utterance():
    """A multi-sentence cache miss (e.g. an LLM follow-up) must stream each
    batch out as soon as it is ready, not wait for every batch to finish."""
    synthesizer = KokoroSynthesizer(model_path="unused", voices_path="unused")

    async def _ensure_ready() -> None:
        return None

    second_batch_released = asyncio.Event()
    yielded_first_batch = asyncio.Event()

    async def _create_stream(text: str, voice: str, speed: float, lang: str):
        yield _BATCH, 24000
        yielded_first_batch.set()
        await second_batch_released.wait()
        yield _BATCH * 2, 24000

    synthesizer.ensure_ready = _ensure_ready  # type: ignore[method-assign]
    synthesizer.kokoro = type(
        "FakeKokoro", (), {"create_stream": staticmethod(_create_stream)}
    )()

    seen_chunks: list[bytes] = []

    async def consume():
        async for chunk in synthesizer.synthesize("Two sentences. Second one."):
            seen_chunks.append(chunk)

    consumer_task = asyncio.create_task(consume())

    await asyncio.wait_for(yielded_first_batch.wait(), timeout=1.0)
    # The first batch must already be visible to the consumer while the
    # second batch is still pending — proof this is real incremental
    # synthesis, not "collect everything, then yield".
    assert seen_chunks
    assert len(synthesizer._cache) == 0  # not cached until the stream finishes

    second_batch_released.set()
    await asyncio.wait_for(consumer_task, timeout=1.0)

    assert len(seen_chunks) > len(set(seen_chunks[:1]))
    assert "Two sentences. Second one." in synthesizer._cache
    assert synthesizer._cache["Two sentences. Second one."] == seen_chunks


@pytest.mark.asyncio
async def test_synthesize_holds_synth_lock_for_the_full_stream_not_just_first_chunk():
    """Regression guard: a second cache-miss call for *different* text must
    not start on the shared Kokoro instance until the first stream has fully
    finished, even though the first stream yields its batches incrementally
    (kokoro_onnx keeps a background task feeding it for as long as it's
    being consumed, so releasing the lock between batches would still race)."""
    synthesizer = KokoroSynthesizer(model_path="unused", voices_path="unused")

    async def _ensure_ready() -> None:
        return None

    first_batch_yielded = asyncio.Event()
    let_first_stream_finish = asyncio.Event()
    started: list[str] = []

    async def _create_stream(text: str, voice: str, speed: float, lang: str):
        started.append(text)
        if text == "First":
            yield _BATCH, 24000
            first_batch_yielded.set()
            await let_first_stream_finish.wait()
        yield _BATCH, 24000

    synthesizer.ensure_ready = _ensure_ready  # type: ignore[method-assign]
    synthesizer.kokoro = type(
        "FakeKokoro", (), {"create_stream": staticmethod(_create_stream)}
    )()

    async def drain(text: str):
        return [chunk async for chunk in synthesizer.synthesize(text)]

    first_task = asyncio.create_task(drain("First"))
    second_task = asyncio.create_task(drain("Second"))

    await asyncio.wait_for(first_batch_yielded.wait(), timeout=1.0)
    # First's stream has produced audio but not finished; Second must still
    # be waiting on the lock, not mid-synthesis.
    assert started == ["First"]

    let_first_stream_finish.set()
    results = await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=1.0)

    assert started == ["First", "Second"]
    assert results[0] and results[1]
