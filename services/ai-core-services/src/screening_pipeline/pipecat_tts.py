"""Pipecat TTS adapter for the existing local Kokoro client."""

from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Iterable

import httpx
import numpy as np

from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

from src.core.config import settings
from src.core.logger import logger


# PCM for bot lines that are identical in every interview (greeting, closing,
# fillers, ...), synthesized once at service startup so the bot can speak its
# greeting the moment it joins.
_shared_phrase_audio: dict[str, list[bytes]] = {}

# One Kokoro model for the whole process, loaded at startup. Loading it holds
# the GIL for ~10-25s even off the event loop, which froze every live
# interview (and timed out Pipecat's pipeline setup) when each session or
# pre-warm loaded its own copy. The ONNX session is not safe to call
# concurrently, so every synthesizer using it shares one lock.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_BREAK = re.compile(r"(?<=[,;:])\s+")
# Phrases shorter than this are joined to the next one: very short pieces
# sound choppy and cost a model call each.
MIN_PHRASE_CHARS = 30
# Sentences longer than this are split at commas / semicolons too.
MAX_PHRASE_CHARS = 90


def split_for_streaming(text: str) -> list[str]:
    """Split text into short phrases, at sentence ends and (for long
    sentences) clause breaks, so synthesis can start playing early."""
    phrases: list[str] = []
    for sentence in _SENTENCE_END.split(text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        parts = (
            _CLAUSE_BREAK.split(sentence)
            if len(sentence) > MAX_PHRASE_CHARS
            else [sentence]
        )
        current = ""
        for part in parts:
            current = f"{current} {part}".strip() if current else part
            if len(current) >= MIN_PHRASE_CHARS:
                phrases.append(current)
                current = ""
        if current:
            if phrases and len(current) < MIN_PHRASE_CHARS:
                phrases[-1] = f"{phrases[-1]} {current}"
            else:
                phrases.append(current)
    return phrases or [text]


class _SynthesisLock:
    """One ONNX session at a time, with live speech ahead of background warming.

    A pre-warm synthesizing a session's ~25 lines took minutes; a question the
    candidate was waiting to hear queued behind it (~30s in a live test).
    Background holders give way whenever a live request is waiting; a line
    already being synthesized still finishes first.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._live_waiting = 0
        self._no_live_waiting = asyncio.Event()
        self._no_live_waiting.set()

    @asynccontextmanager
    async def hold(self, *, live: bool):
        if live:
            self._live_waiting += 1
            self._no_live_waiting.clear()
            try:
                await self._lock.acquire()
            finally:
                self._live_waiting -= 1
                if self._live_waiting == 0:
                    self._no_live_waiting.set()
        else:
            while True:
                await self._no_live_waiting.wait()
                await self._lock.acquire()
                if self._live_waiting == 0:
                    break
                self._lock.release()  # a live request arrived meanwhile
        try:
            yield
        finally:
            self._lock.release()


_shared_model = None
_shared_model_lock: _SynthesisLock | None = None


def _shared_synth_lock() -> _SynthesisLock:
    global _shared_model_lock
    if _shared_model_lock is None:
        _shared_model_lock = _SynthesisLock()
    return _shared_model_lock


async def warm_shared_phrases(synthesizer: "KokoroSynthesizer", texts: Iterable[str]) -> None:
    """Synthesize fixed bot lines once and share them with every interview."""
    for text in texts:
        if not text or text in _shared_phrase_audio:
            continue
        chunks = [chunk async for chunk in synthesizer.synthesize(text, background=True)]
        _shared_phrase_audio[text] = chunks
    logger.info("Shared bot phrases ready", extra={"phrases": len(_shared_phrase_audio)})


class KokoroSynthesizer:
    """Pipecat-owned local Kokoro model lifecycle and PCM synthesis."""

    def __init__(self, model_path: str | None = None, voices_path: str | None = None):
        model_root = settings.ai_models_host_dir or "/app/.models"
        self.model_path = model_path or settings.kokoro_model_path or os.path.join(
            model_root, "kokoro", "kokoro-v1.0.onnx"
        )
        self.voices_path = voices_path or settings.kokoro_voices_path or os.path.join(
            model_root, "kokoro", "voices-v1.0.bin"
        )
        self.kokoro = None
        self._download_lock = asyncio.Lock()
        # Per-session PCM cache for known bot text (greeting, questions, closing,
        # etc.), keyed by exact synthesized string. One synthesizer instance is
        # created per Pipecat session (see PipecatInterviewRuntime), so this cache
        # is naturally scoped to a single meeting and discarded with it.
        self._cache: dict[str, list[bytes]] = {}
        # Kokoro's onnxruntime session is not safe to invoke concurrently from
        # multiple threads; serialize both warm-up and live synthesis through it.
        self._synth_lock = _SynthesisLock()
        self._load_lock = asyncio.Lock()

    def _artifacts_present(self) -> bool:
        return os.path.exists(self.model_path) and os.path.exists(self.voices_path)

    async def _load_model(self) -> None:
        """Use the process-wide model, loading it only if startup didn't."""
        global _shared_model
        if _shared_model is None:
            from kokoro_onnx import Kokoro

            _shared_model = await asyncio.to_thread(Kokoro, self.model_path, self.voices_path)
        self.kokoro = _shared_model
        self._synth_lock = _shared_synth_lock()

    async def prepare(self) -> None:
        """Make the model usable before live audio starts.

        Instant when the shared model was loaded at startup. Raises when the
        artifacts are missing and can't be downloaded, so the session fails
        instead of leaving a silent bot in the meeting.
        """
        await self.ensure_ready()

    async def ensure_ready(self) -> None:
        if self.kokoro is not None:
            return
        async with self._load_lock:
            await self._ensure_ready_locked()

    async def _ensure_ready_locked(self) -> None:
        if self.kokoro is not None:
            return
        if _shared_model is not None or self._artifacts_present():
            await self._load_model()
            return

        if not settings.kokoro_allow_download:
            raise FileNotFoundError(
                "Kokoro artifacts are missing. Configure KOKORO_MODEL_PATH and "
                "KOKORO_VOICES_PATH, or enable KOKORO_ALLOW_DOWNLOAD."
            )

        async with self._download_lock:
            if not (os.path.exists(self.model_path) and os.path.exists(self.voices_path)):
                logger.info("Downloading Pipecat Kokoro model artifacts")
                model_directory = os.path.dirname(self.model_path)
                if model_directory:
                    os.makedirs(model_directory, exist_ok=True)
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    model = await client.get(
                        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
                        "model-files-v1.0/kokoro-v1.0.onnx",
                        timeout=300.0,
                    )
                    model.raise_for_status()
                    with open(self.model_path, "wb") as file:
                        file.write(model.content)
                    voices = await client.get(
                        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
                        "model-files-v1.0/voices-v1.0.bin",
                        timeout=60.0,
                    )
                    voices.raise_for_status()
                    with open(self.voices_path, "wb") as file:
                        file.write(voices.content)
            if self.kokoro is None:
                await self._load_model()

    async def synthesize(
        self, text: str, *, background: bool = False
    ) -> AsyncGenerator[bytes, None]:
        cached = self._cache.get(text)
        if cached is None:
            cached = _shared_phrase_audio.get(text)
        if cached is not None:
            for chunk in cached:
                yield chunk
            return

        # Held for the whole cache-miss synthesis below, not just released
        # between sentences: kokoro_onnx's own create_stream() keeps a
        # background task feeding a one-item-ahead queue for as long as this
        # generator is being consumed, so a second concurrent call sharing
        # this Kokoro instance could still race the onnx session even if we
        # only re-acquired the lock between individual chunk yields.
        async with self._synth_lock.hold(live=not background):
            # Another caller (e.g. a warm-up pass) may have populated the
            # cache while this one waited for the lock.
            cached = self._cache.get(text)
            if cached is not None:
                for chunk in cached:
                    yield chunk
                return

            await self.ensure_ready()
            collected: list[bytes] = []
            async for pcm_bytes in self._stream_pcm(text):
                collected.append(pcm_bytes)
                yield pcm_bytes
            self._cache[text] = collected

    async def _stream_pcm(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize sentence/clause-by-sentence, yielding each batch's audio
        as soon as it finishes instead of blocking on the whole utterance.

        Uses kokoro_onnx's create_stream (rather than create): same voice,
        speed, language, and batching as before, just delivered
        incrementally, so the first audio for a multi-sentence reply (e.g. a
        follow-up question) goes out well before the last sentence has been
        synthesized.
        """
        # Kokoro only splits text longer than ~510 phonemes, so a one- or
        # two-sentence LLM reply was synthesized as one block and nothing
        # played until all of it was ready (25-35s for a 14s explanation,
        # Bug-037). Feed it short phrases so playback starts after the first.
        for phrase in split_for_streaming(text):
            async for samples, _sample_rate in self.kokoro.create_stream(
                phrase, voice="af_bella", speed=1.0, lang="en-us"
            ):
                pcm_bytes = (samples * 32767).astype(np.int16).tobytes()
                for offset in range(0, len(pcm_bytes), 2400):
                    yield pcm_bytes[offset : offset + 2400]

    async def warm(self, texts: Iterable[str]) -> None:
        """Pre-synthesize known bot text so later speak() calls hit the cache.

        Intended to run in the background right after questions are loaded for
        a session (before the candidate has heard the greeting reply), so
        synthesis latency is paid up front instead of on the hot turn path.
        """
        seen: set[str] = set()
        for text in texts:
            if (
                not text
                or text in seen
                or text in self._cache
                or text in _shared_phrase_audio
            ):
                continue
            seen.add(text)
            async for _ in self.synthesize(text, background=True):
                pass


class KokoroTTSService(TTSService):
    """Expose existing Kokoro PCM chunks as Pipecat audio frames."""

    def __init__(
        self,
        synthesizer: KokoroSynthesizer | None = None,
        *,
        sample_rate: int = 24000,
    ):
        super().__init__(
            sample_rate=sample_rate,
            settings=TTSSettings(
                model="kokoro-v1.0",
                voice="af_bella",
                language="en-us",
            ),
        )
        self.synthesizer = synthesizer or KokoroSynthesizer()
        self._output_sample_rate = sample_rate

    async def validate_ready(self) -> None:
        """Attach the shared Kokoro model (loaded at startup) before live audio starts."""
        await self.synthesizer.prepare()

    async def warm_cache(self, texts: Iterable[str]) -> None:
        """Pre-synthesize known bot text for this session. See KokoroSynthesizer.warm."""
        await self.synthesizer.warm(texts)

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        async for audio in self.synthesizer.synthesize(text):
            yield TTSAudioRawFrame(
                audio=audio,
                sample_rate=self._output_sample_rate,
                num_channels=1,
                context_id=context_id,
            )
