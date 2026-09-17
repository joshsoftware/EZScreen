"""Pipecat STT adapter for the existing Whisper HTTP transcription contract."""

from __future__ import annotations

import io
import wave
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.services.stt_service import STTService

from src.core.config import settings
from src.core.logger import logger


class WhisperHttpSTTService(STTService):
    """Transcribe finalized audio segments using the existing Whisper endpoint."""

    def __init__(self, *, sample_rate: int = 24000):
        super().__init__(audio_passthrough=False, sample_rate=sample_rate)
        self.sample_rate = sample_rate

    @staticmethod
    def _wav_bytes(audio: bytes, sample_rate: int) -> bytes:
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio)
        return wav_io.getvalue()

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        if len(audio) < 24000:
            return

        wav_bytes = self._wav_bytes(audio, self.sample_rate)
        headers = {"Authorization": f"Bearer {settings.whisper_api_key}"}
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {
            "model": "whisper-large-v3",
            "response_format": "json",
            "language": "en",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.whisper_api_url
                    or "https://api.groq.com/openai/v1/audio/transcriptions",
                    files=files,
                    data=data,
                    headers=headers,
                )
                response.raise_for_status()
                transcript = response.json().get("text", "").strip()
        except Exception as error:
            logger.error("Pipecat Whisper transcription failed", extra={"error": str(error)})
            return

        if transcript:
            yield TranscriptionFrame(
                text=transcript,
                user_id="candidate",
                timestamp=datetime.now(timezone.utc).isoformat(),
                finalized=True,
            )