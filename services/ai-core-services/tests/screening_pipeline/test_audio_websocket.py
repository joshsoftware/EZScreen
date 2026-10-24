import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.audio_websocket import (
    _should_forward_candidate_audio,
    _run_pipecat_session,
)
from src.screening_pipeline.pipecat_transport import (
    decode_attendee_audio_message,
    encode_attendee_audio_message,
)


def test_mixed_audio_is_forwarded_for_the_whole_candidate_turn():
    # Bug-042: a candidate continuing after a pause ("collecting_answer") or
    # while their answer is being evaluated must still be heard.
    for state in ("listening", "collecting_answer", "evaluating", "closing"):
        assert _should_forward_candidate_audio("realtime_audio.mixed", state, False)
    assert not _should_forward_candidate_audio("realtime_audio.mixed", "speaking", False)


def test_mixed_audio_is_dropped_while_the_bot_voice_is_playing():
    # e.g. a filler during evaluation: the mixed audio contains the bot itself.
    assert not _should_forward_candidate_audio(
        "realtime_audio.mixed", "evaluating", False, bot_audible=True
    )
    assert _should_forward_candidate_audio(
        "realtime_audio.user", "evaluating", False, bot_audible=True
    )


def test_user_audio_is_preferred_over_mixed_audio():
    assert _should_forward_candidate_audio("realtime_audio.user", "speaking", False)
    assert not _should_forward_candidate_audio("realtime_audio.mixed", "listening", True)


def test_pipecat_attendee_codec_preserves_audio_payload_and_rate():
    encoded = encode_attendee_audio_message(b"pcm", sample_rate=24000)

    decoded = decode_attendee_audio_message(encoded)

    assert decoded is not None
    assert decoded.trigger == "realtime_audio.bot_output"
    assert decoded.pcm_bytes == b"pcm"
    assert decoded.sample_rate == 24000


def test_pipecat_attendee_codec_rejects_invalid_audio_messages():
    assert decode_attendee_audio_message({"trigger": "realtime_audio.user"}) is None
    assert decode_attendee_audio_message(
        {
            "trigger": "realtime_audio.user",
            "data": {"chunk": "not-base64!", "sample_rate": 24000},
        }
    ) is None


@pytest.mark.asyncio
async def test_pipecat_websocket_branch_preserves_attendee_audio_selection():
    class FakeWebSocket:
        def __init__(self):
            self.messages = [
                {
                    "text": json.dumps(
                        {
                            "trigger": "realtime_audio.mixed",
                            "data": {
                                "chunk": base64.b64encode(b"mixed-before").decode(),
                                "sample_rate": 24000,
                            },
                        }
                    )
                },
                {
                    "text": json.dumps(
                        {
                            "trigger": "realtime_audio.user",
                            "data": {
                                "chunk": base64.b64encode(b"user-audio").decode(),
                                "sample_rate": 16000,
                            },
                        }
                    )
                },
                {
                    "text": json.dumps(
                        {
                            "trigger": "realtime_audio.mixed",
                            "data": {
                                "chunk": base64.b64encode(b"mixed-after").decode(),
                                "sample_rate": 24000,
                            },
                        }
                    )
                },
                {"bytes": b"binary-audio"},
                {"type": "websocket.disconnect"},
            ]

        async def receive(self):
            return self.messages.pop(0)

    created_runtimes = []

    class FakeRuntime:
        def __init__(self, **_kwargs):
            self.policy = MagicMock(current_interaction_state="listening")
            self.push_audio = AsyncMock()
            self.cleanup = AsyncMock()
            created_runtimes.append(self)

        async def run(self):
            return None

    websocket = FakeWebSocket()
    with patch(
        "src.screening_pipeline.pipecat_runtime.PipecatInterviewRuntime",
        FakeRuntime,
    ):
        await _run_pipecat_session(websocket, "session-id")

    runtime = created_runtimes[0]
    assert runtime.push_audio.await_args_list == [
        ((b"mixed-before", 24000),),
        ((b"user-audio", 16000),),
        ((b"binary-audio", 24000),),
    ]
    runtime.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_crashed_runtime_closes_the_stream_instead_of_idling_muted():
    class SilentWebSocket:
        """Attendee keeps the socket open and may send nothing for a while."""

        def __init__(self):
            self.closed = False

        async def receive(self):
            await asyncio.Event().wait()

        async def close(self):
            self.closed = True

    created_runtimes = []

    class CrashingRuntime:
        def __init__(self, **_kwargs):
            self.policy = MagicMock(current_interaction_state="listening")
            self.push_audio = AsyncMock()
            self.cleanup = AsyncMock()
            created_runtimes.append(self)

        async def run(self):
            raise FileNotFoundError("Kokoro artifacts are missing")

    websocket = SilentWebSocket()
    with patch(
        "src.screening_pipeline.pipecat_runtime.PipecatInterviewRuntime",
        CrashingRuntime,
    ):
        await asyncio.wait_for(_run_pipecat_session(websocket, "session-id"), timeout=2)

    assert websocket.closed
    created_runtimes[0].cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_output_tracks_how_long_the_bot_voice_plays(monkeypatch):
    from pipecat.frames.frames import OutputAudioRawFrame
    from pipecat.processors.frame_processor import FrameDirection
    from src.screening_pipeline import pipecat_transport
    from src.screening_pipeline.pipecat_transport import AttendeeOutputProcessor

    clock = {"now": 100.0}
    monkeypatch.setattr(pipecat_transport.time, "monotonic", lambda: clock["now"])
    output = AttendeeOutputProcessor(MagicMock(send_json=AsyncMock()))
    output.push_frame = AsyncMock()
    assert not output.is_bot_audible()

    one_second = bytes(2 * 24000)
    await output.process_frame(
        OutputAudioRawFrame(audio=one_second, sample_rate=24000, num_channels=1),
        FrameDirection.DOWNSTREAM,
    )

    clock["now"] = 100.9
    assert output.is_bot_audible()
    clock["now"] = 101.0 + AttendeeOutputProcessor.ECHO_TAIL_SECONDS + 0.01
    assert not output.is_bot_audible()


@pytest.mark.asyncio
async def test_wait_until_played_waits_for_playback_and_stops_on_barge_in():
    from pipecat.frames.frames import InterruptionFrame, OutputAudioRawFrame
    from pipecat.processors.frame_processor import FrameDirection
    from src.screening_pipeline.pipecat_transport import AttendeeOutputProcessor

    output = AttendeeOutputProcessor(MagicMock(send_json=AsyncMock()))
    output.push_frame = AsyncMock()
    tenth_of_a_second = bytes(2 * 2400)  # 0.1s at 24 kHz
    await output.process_frame(
        OutputAudioRawFrame(audio=tenth_of_a_second * 3, sample_rate=24000, num_channels=1),
        FrameDirection.DOWNSTREAM,
    )

    loop = asyncio.get_running_loop()
    started = loop.time()
    await asyncio.wait_for(output.wait_until_played(), timeout=2)
    assert loop.time() - started >= 0.25  # ~0.3s of speech

    await output.process_frame(
        OutputAudioRawFrame(audio=tenth_of_a_second * 50, sample_rate=24000, num_channels=1),
        FrameDirection.DOWNSTREAM,
    )
    waiter = asyncio.create_task(output.wait_until_played())
    await asyncio.sleep(0.05)
    await output.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    await asyncio.wait_for(waiter, timeout=1)  # did not wait out 5s of speech
