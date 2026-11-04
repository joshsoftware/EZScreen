"""One interviewer per screening (Bugs 44-46).

Attendee reconnected the audio stream as the bot left. The new connection
started a second runtime with an empty memory; it received the bot's "ended"
webhook and saved "No answers were scored: the candidate did not join the
meeting or never spoke" (0.0 overall, 0.0 per category) over the real result
of a 20-minute interview.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline import audio_websocket
from src.screening_pipeline.finished_interviews import _finished_bots
from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy


@pytest.fixture(autouse=True)
def _clean_registries():
    _finished_bots.clear()
    audio_websocket.active_sessions.clear()
    yield
    _finished_bots.clear()
    audio_websocket.active_sessions.clear()


def _session(bot_id="bot-1"):
    return MagicMock(
        id="sess-1",
        status="in_progress",
        generated_questions=[],
        interview_metadata={"bot_id": bot_id},
    )


def _policy():
    api_client = MagicMock()
    api_client.update_status = AsyncMock(return_value=True)
    policy = PipecatInterviewPolicy(
        "sess-1",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        speech_output=AsyncMock(),
    )
    policy._leave_bot_after_close = AsyncMock()
    return policy


async def _start(policy, session):
    with patch(
        "src.screening_pipeline.pipecat_policy.interview_session_repo.get_by_id",
        AsyncMock(return_value=session),
    ):
        await policy.start()


@pytest.mark.asyncio
async def test_reconnect_after_the_interview_ended_does_not_start_or_save():
    first = _policy()
    await _start(first, _session())
    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()), patch(
        "src.screening_pipeline.pipecat_policy.SessionApiClient"
    ):
        await first.end_interview("meeting_ended")

    # The session row still says in_progress: the first runtime has not
    # written "completed" yet when Attendee reconnects.
    second = _policy()
    await _start(second, _session())

    assert second.is_active is False
    assert second.api_client is None
    with patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()
    ) as close:
        await second.end_interview("meeting_ended")
    close.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_rescheduled_session_with_a_new_bot_starts_normally():
    first = _policy()
    await _start(first, _session("bot-old"))
    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()), patch(
        "src.screening_pipeline.pipecat_policy.SessionApiClient"
    ):
        await first.end_interview("meeting_ended")

    rescheduled = _policy()
    await _start(rescheduled, _session("bot-new"))

    assert rescheduled.is_active is True
    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()):
        await rescheduled.end_interview("test")


@pytest.mark.asyncio
async def test_second_connection_does_not_replace_a_running_interview():
    running = MagicMock()
    running.policy.is_active = True
    audio_websocket.active_sessions["sess-1"] = running
    websocket = MagicMock()
    websocket.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

    with patch("src.screening_pipeline.pipecat_runtime.PipecatInterviewRuntime") as runtime_cls:
        await audio_websocket._run_pipecat_session(websocket, "sess-1")

    runtime_cls.assert_not_called()
    assert audio_websocket.active_sessions["sess-1"] is running


@pytest.mark.asyncio
async def test_closing_connection_keeps_a_newer_runtime_registered():
    newer = MagicMock()

    class _Runtime:
        def __init__(self, websocket, session_id):
            self.policy = MagicMock(is_active=False)
            self.output = None

        async def run(self):
            return None

        async def cleanup(self):
            # A newer connection registered while this one was closing.
            audio_websocket.active_sessions["sess-1"] = newer

    websocket = MagicMock()
    websocket.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

    with patch("src.screening_pipeline.pipecat_runtime.PipecatInterviewRuntime", _Runtime):
        await audio_websocket._run_pipecat_session(websocket, "sess-1")

    assert audio_websocket.active_sessions["sess-1"] is newer
