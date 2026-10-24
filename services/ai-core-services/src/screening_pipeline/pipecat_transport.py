"""Attendee audio protocol helpers for the Pipecat runtime."""

from __future__ import annotations

import asyncio
import base64
import time
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

    # Attendee plays our audio into the meeting a little after we send it, and
    # it comes back in the mixed meeting audio slightly later still.
    ECHO_TAIL_SECONDS = 0.6

    def __init__(self, websocket, *, chunk_size: int = 2400):
        super().__init__(name="attendee-output")
        self.websocket = websocket
        self.chunk_size = chunk_size
        self._pending_events: set[asyncio.Event] = set()
        # Monotonic time until which the bot's sent audio is still playing.
        self._playing_until = 0.0
        # Bumped on every barge-in, so waits for playback can stop early.
        self._interruptions = 0

    def is_bot_audible(self) -> bool:
        """True while the bot's own voice may be in the mixed meeting audio."""
        return time.monotonic() < self._playing_until + self.ECHO_TAIL_SECONDS

    async def wait_until_played(self) -> None:
        """Return once the audio sent so far has finished playing, or on barge-in.

        Sending audio to Attendee is near-instant; playing it takes as long as
        the speech. Silence timers started on send ran during the bot's own
        speech (the 15s after a 7s greeting felt like 8s).
        """
        interruptions = self._interruptions
        while self._interruptions == interruptions:
            remaining = self._playing_until - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 0.25))

    def _track_playback(self, num_bytes: int, sample_rate: int, num_channels: int) -> None:
        if sample_rate <= 0:
            return
        seconds = num_bytes / (sample_rate * 2 * max(num_channels, 1))
        self._playing_until = max(time.monotonic(), self._playing_until) + seconds

    def register_speech_event(self, event: asyncio.Event) -> None:
        """Track an utterance before its completion marker reaches the output."""
        self._pending_events.add(event)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, AudioRawFrame):
            for start in range(0, len(frame.audio), self.chunk_size):
                chunk = frame.audio[start : start + self.chunk_size]
                await self.websocket.send_json(
                    encode_attendee_audio_message(chunk, sample_rate=frame.sample_rate)
                )
                self._track_playback(len(chunk), frame.sample_rate, frame.num_channels)
        elif isinstance(frame, SpeechCompleteFrame):
            self._pending_events.discard(frame.event)
            frame.event.set()
        elif isinstance(frame, InterruptionFrame):
            self._interruptions += 1
            for event in self._pending_events:
                event.set()
            self._pending_events.clear()
        await self.push_frame(frame, direction)
