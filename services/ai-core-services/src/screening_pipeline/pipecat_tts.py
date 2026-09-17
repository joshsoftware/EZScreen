"""Pipecat TTS adapter for the existing local Kokoro client."""

from __future__ import annotations

from typing import AsyncGenerator

from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

from src.screening_pipeline.tts_client import (
    LocalKokoroTTSClient,
    get_shared_kokoro_client,
)


class KokoroTTSService(TTSService):
    """Expose existing Kokoro PCM chunks as Pipecat audio frames."""

    def __init__(
        self,
        client: LocalKokoroTTSClient | None = None,
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
        self.client = client or get_shared_kokoro_client()
        self._output_sample_rate = sample_rate

    async def validate_ready(self) -> None:
        """Load externally provisioned Kokoro artifacts before live audio starts."""
        await self.client._ensure_models()

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        async for audio in self.client.synthesize(text):
            yield TTSAudioRawFrame(
                audio=audio,
                sample_rate=self._output_sample_rate,
                num_channels=1,
                context_id=context_id,
            )