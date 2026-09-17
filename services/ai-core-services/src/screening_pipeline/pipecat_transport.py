"""Attendee audio protocol helpers for the Pipecat runtime."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass

from pipecat.frames.frames import AudioRawFrame, Frame, InterruptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


@dataclass
class SpeechCompleteFrame(Frame):
    """Marker frame pushed downstream to signal when speech audio has finished streaming."""

    event: asyncio.Event


@dataclass(frozen=True)
class AttendeeAudioChunk:
    """Decoded audio received from an Attendee WebSocket message."""

    trigger: str
    pcm_bytes: bytes
    sample_rate: int


def decode_attendee_audio_message(message: dict) -> AttendeeAudioChunk | None:
    """Decode one base64 audio message without applying interview state policy."""
    trigger = message.get("trigger") or message.get("event") or message.get("type")
    data = message.get("data")
    if not isinstance(trigger, str) or not isinstance(data, dict):
        return None

    chunk = data.get("chunk")
    if not isinstance(chunk, str) or not chunk:
        return None

    try:
        pcm_bytes = base64.b64decode(chunk, validate=True)
    except (ValueError, TypeError):
        return None

    sample_rate = data.get("sample_rate", 24000)
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        return None

    return AttendeeAudioChunk(trigger, pcm_bytes, sample_rate)


def encode_attendee_audio_message(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 24000,
) -> dict:
    """Encode one outbound Attendee audio message."""
    return {
        "trigger": "realtime_audio.bot_output",
        "data": {
            "chunk": base64.b64encode(pcm_bytes).decode("ascii"),
            "sample_rate": sample_rate,
        },
    }


class AttendeeOutputProcessor(FrameProcessor):
    """Serialize Pipecat audio frames to Attendee in ordered 50 ms chunks."""

    def __init__(self, websocket, *, chunk_size: int = 2400):
        super().__init__(name="attendee-output")
        self.websocket = websocket
        self.chunk_size = chunk_size
        self._pending_events: set[asyncio.Event] = set()

    def register_speech_event(self, event: asyncio.Event) -> None:
        """Track an utterance before its completion marker reaches the output."""
        self._pending_events.add(event)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, AudioRawFrame):
            for start in range(0, len(frame.audio), self.chunk_size):
                await self.websocket.send_json(
                    encode_attendee_audio_message(
                        frame.audio[start : start + self.chunk_size],
                        sample_rate=frame.sample_rate,
                    )
                )
        elif isinstance(frame, SpeechCompleteFrame):
            self._pending_events.discard(frame.event)
            frame.event.set()
        elif isinstance(frame, InterruptionFrame):
            for event in self._pending_events:
                event.set()
            self._pending_events.clear()
        await self.push_frame(frame, direction)
