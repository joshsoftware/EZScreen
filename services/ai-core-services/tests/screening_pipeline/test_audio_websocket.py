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


def test_mixed_audio_is_used_as_fallback_only_while_listening_or_closing():
    assert _should_forward_candidate_audio("realtime_audio.mixed", "listening", False)
    assert _should_forward_candidate_audio("realtime_audio.mixed", "closing", False)
    assert not _should_forward_candidate_audio("realtime_audio.mixed", "speaking", False)


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
