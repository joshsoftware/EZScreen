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


@pytest.mark.asyncio
async def test_shared_phrases_play_without_the_session_model(monkeypatch):
    """The greeting must be speakable the moment the bot joins, before this
    session's own Kokoro model has loaded."""
    from src.screening_pipeline import pipecat_tts

    monkeypatch.setattr(pipecat_tts, "_shared_phrase_audio", {"Hi!": [b"warm-greeting"]})
    synthesizer = KokoroSynthesizer(model_path="unused", voices_path="unused")
    synthesizer.ensure_ready = None  # would blow up if called

    assert [chunk async for chunk in synthesizer.synthesize("Hi!")] == [b"warm-greeting"]


@pytest.mark.asyncio
async def test_warm_shared_phrases_synthesizes_each_fixed_line_once(monkeypatch):
    from src.screening_pipeline import pipecat_tts

    monkeypatch.setattr(pipecat_tts, "_shared_phrase_audio", {})
    create_calls: list[str] = []
    synthesizer = _make_synthesizer_with_fake_model(create_calls)

    await pipecat_tts.warm_shared_phrases(synthesizer, ["Hi!", "Bye.", "Hi!"])

    assert create_calls == ["Hi!", "Bye."]
    assert set(pipecat_tts._shared_phrase_audio) == {"Hi!", "Bye."}

    # A session warm-up then skips the shared lines entirely.
    other_calls: list[str] = []
    session = _make_synthesizer_with_fake_model(other_calls)
    await session.warm(["Hi!", "Question 1"])
    assert other_calls == ["Question 1"]


@pytest.mark.asyncio
async def test_sessions_share_one_model_and_one_lock(tmp_path, monkeypatch):
    """Each session must reuse the startup model; loading a model per session
    froze ai-core long enough to time out Pipecat's pipeline setup."""
    from src.screening_pipeline import pipecat_tts

    shared = object()
    monkeypatch.setattr(pipecat_tts, "_shared_model", shared)
    monkeypatch.setattr(pipecat_tts, "_shared_model_lock", None)
    first = KokoroSynthesizer(model_path=str(tmp_path / "gone.onnx"), voices_path=str(tmp_path / "gone.bin"))
    second = KokoroSynthesizer(model_path=str(tmp_path / "gone.onnx"), voices_path=str(tmp_path / "gone.bin"))

    await asyncio.wait_for(first.prepare(), timeout=1)
    await asyncio.wait_for(second.prepare(), timeout=1)

    assert first.kokoro is shared and second.kokoro is shared
    assert first._synth_lock is second._synth_lock


@pytest.mark.asyncio
async def test_prepare_fails_fast_when_artifacts_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.screening_pipeline.pipecat_tts.settings.kokoro_allow_download", False)
    synthesizer = KokoroSynthesizer(
        model_path=str(tmp_path / "missing.onnx"), voices_path=str(tmp_path / "missing.bin")
    )

    with pytest.raises(FileNotFoundError, match="Kokoro artifacts are missing"):
        await synthesizer.prepare()


@pytest.mark.asyncio
async def test_live_speech_jumps_ahead_of_background_warming():
    """A question the candidate is waiting for must not queue behind the
    pre-warm's remaining lines (~30s in a live test)."""
    synthesizer = KokoroSynthesizer(model_path="unused", voices_path="unused")
    order: list[str] = []
    release_first = asyncio.Event()

    async def _ensure_ready() -> None:
        return None

    async def _create_stream(text: str, voice: str, speed: float, lang: str):
        order.append(text)
        if text == "warm-1":
            await release_first.wait()
        yield _BATCH, 24000

    synthesizer.ensure_ready = _ensure_ready  # type: ignore[method-assign]
    synthesizer.kokoro = type("FakeKokoro", (), {"create_stream": staticmethod(_create_stream)})()

    warming = asyncio.create_task(synthesizer.warm(["warm-1", "warm-2", "warm-3"]))
    await asyncio.sleep(0.05)  # warm-1 in progress
    live = asyncio.create_task(_drain(synthesizer, "Question 1?"))
    await asyncio.sleep(0.05)
    release_first.set()
    await asyncio.wait_for(asyncio.gather(warming, live), timeout=2)

    assert order == ["warm-1", "Question 1?", "warm-2", "warm-3"]


async def _drain(synthesizer, text):
    return [chunk async for chunk in synthesizer.synthesize(text)]


def test_llm_replies_are_split_into_short_phrases():
    from src.screening_pipeline.pipecat_tts import split_for_streaming

    text = (
        "Sure. I am asking how you handle exceptions globally in a Spring Boot REST API, "
        "for example using a ControllerAdvice class with ExceptionHandler methods, "
        "and how you return consistent error responses to the client."
    )

    assert split_for_streaming(text) == [
        "Sure.",
        "I am asking how you handle exceptions globally in a Spring Boot REST API,",
        "for example using a ControllerAdvice class with ExceptionHandler methods,",
        "and how you return consistent error responses to the client.",
    ]
    assert split_for_streaming("Could you explain more?") == ["Could you explain more?"]
    # Tiny trailing pieces are joined rather than synthesized on their own.
    assert split_for_streaming("Okay. Got it.") == ["Okay. Got it."]


@pytest.mark.asyncio
async def test_first_phrase_plays_before_the_rest_is_synthesized():
    """Bug-037: a one-sentence explanation was synthesized as a single block,
    so nothing played for 25-35s."""
    synthesizer = KokoroSynthesizer(model_path="unused", voices_path="unused")
    started: list[str] = []
    release = asyncio.Event()

    async def _ensure_ready() -> None:
        return None

    async def _create_stream(text: str, voice: str, speed: float, lang: str):
        started.append(text)
        if len(started) > 1:
            await release.wait()
        yield _BATCH, 24000

    synthesizer.ensure_ready = _ensure_ready  # type: ignore[method-assign]
    synthesizer.kokoro = type("FakeKokoro", (), {"create_stream": staticmethod(_create_stream)})()

    stream = synthesizer.synthesize(
        "Sure. I am asking how you handle exceptions globally in a Spring Boot REST API, "
        "and how you return consistent error responses."
    )
    first = await asyncio.wait_for(stream.__anext__(), timeout=1)
    assert first and started == ["Sure."]

    release.set()
    rest = [chunk async for chunk in stream]
    assert rest and len(started) == 3
