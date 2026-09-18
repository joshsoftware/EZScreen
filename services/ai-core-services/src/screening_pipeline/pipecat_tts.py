"""Pipecat TTS adapter for the existing local Kokoro client."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

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
        await self.ensure_ready()
        loop = asyncio.get_running_loop()
        samples, _sample_rate = await loop.run_in_executor(
            None,
            lambda: self.kokoro.create(text, voice="af_bella", speed=1.0, lang="en-us"),
        )
        pcm_bytes = (samples * 32767).astype(np.int16).tobytes()
        for offset in range(0, len(pcm_bytes), 2400):
            yield pcm_bytes[offset : offset + 2400]


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

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        async for audio in self.synthesizer.synthesize(text):
            yield TTSAudioRawFrame(
                audio=audio,
                sample_rate=self._output_sample_rate,
                num_channels=1,
                context_id=context_id,
            )
