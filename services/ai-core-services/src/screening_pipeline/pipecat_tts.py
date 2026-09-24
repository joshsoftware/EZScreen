"""Pipecat TTS adapter for the existing local Kokoro client."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator, Iterable

import httpx
import numpy as np

from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

from src.core.config import settings
from src.core.logger import logger


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
        self._synth_lock = asyncio.Lock()

    async def ensure_ready(self) -> None:
        if os.path.exists(self.model_path) and os.path.exists(self.voices_path):
            if self.kokoro is None:
                from kokoro_onnx import Kokoro

                self.kokoro = Kokoro(self.model_path, self.voices_path)
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
                from kokoro_onnx import Kokoro

                self.kokoro = Kokoro(self.model_path, self.voices_path)

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        cached = self._cache.get(text)
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
        async with self._synth_lock:
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
        async for samples, _sample_rate in self.kokoro.create_stream(
            text, voice="af_bella", speed=1.0, lang="en-us"
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
            if not text or text in seen or text in self._cache:
                continue
            seen.add(text)
            async for _ in self.synthesize(text):
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
        """Load externally provisioned Kokoro artifacts before live audio starts."""
        await self.synthesizer.ensure_ready()

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
