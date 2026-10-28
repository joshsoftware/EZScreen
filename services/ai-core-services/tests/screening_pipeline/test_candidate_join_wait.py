"""The bot waits in the meeting for the candidate before greeting.

A candidate who joined a few minutes late found the bot gone: it greeted an
empty meeting, asked the first question and left after ~2 minutes of silence.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.candidate_presence import (
    forget_session,
    is_candidate_present,
    mark_candidate_joined,
)
from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy
from src.screening_pipeline.prompts import GREETING_TEXT
from src.screening_pipeline.webhook_handler import process_participant_event


def _policy(session_id="sess-join"):
    api_client = MagicMock()
    api_client.update_status = AsyncMock(return_value=True)
    policy = PipecatInterviewPolicy(
        session_id,
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )
    policy._leave_bot_after_close = AsyncMock()
    return policy


async def _start(policy):
    session = MagicMock(id=policy.session_id, status="in_progress", generated_questions=[])
    with patch(
        "src.screening_pipeline.pipecat_policy.interview_session_repo.get_by_id",
        AsyncMock(return_value=session),
    ):
        await policy.start()


def _spoken(policy):
    return [call.args[0] for call in policy.speech_output.await_args_list]


@pytest.fixture(autouse=True)
def _clean_presence():
    forget_session("sess-join")
    yield
    forget_session("sess-join")


@pytest.mark.asyncio
async def test_bot_waits_silently_until_the_candidate_joins():
    policy = _policy()
    await _start(policy)

    assert policy.current_interaction_state == "waiting_for_candidate"
    assert _spoken(policy) == []

    await policy.candidate_joined()

    assert _spoken(policy) == [GREETING_TEXT]
    assert policy.current_interaction_state == "listening"
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_candidate_already_in_the_meeting_is_greeted_at_once():
    """Attendee reports people already in the call as the bot joins,
    possibly before the runtime exists."""
    mark_candidate_joined("sess-join")
    policy = _policy()
    await _start(policy)

    assert _spoken(policy) == [GREETING_TEXT]
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_speech_while_waiting_starts_the_interview():
    """Fallback in case the join webhook is missed."""
    policy = _policy()
    await _start(policy)

    policy.handle_candidate_activity()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert _spoken(policy) == [GREETING_TEXT]
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_nobody_joins_within_the_wait_is_a_no_show(monkeypatch):
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.CANDIDATE_JOIN_WAIT_SECONDS", 0)
    policy = _policy()
    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()):
        await _start(policy)
        await policy._candidate_wait_task

    assert _spoken(policy) == []
    assert policy.termination_reason == "candidate_absent"
    policy.api_client.update_status.assert_awaited_once_with("no_show")
    policy._leave_bot_after_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_rescheduled_attempt_does_not_inherit_presence():
    """The session row is reused after a reschedule; the earlier attempt's
    join must not make the next bot greet an empty meeting."""
    mark_candidate_joined("sess-join")
    policy = _policy()
    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()):
        await _start(policy)
        await policy.end_interview("questions_completed")

    assert not is_candidate_present("sess-join")


@pytest.mark.asyncio
async def test_join_webhook_starts_a_waiting_interview():
    policy = _policy()
    await _start(policy)
    runtime = MagicMock()
    runtime.policy = policy
    session = MagicMock(id="sess-join")

    with patch(
        "src.screening_pipeline.webhook_handler.interview_session_repo.get_by_bot_id",
        AsyncMock(return_value=session),
    ), patch("src.screening_pipeline.audio_websocket.active_sessions", {"sess-join": runtime}):
        await process_participant_event(
            {"bot_id": "bot-1", "data": {"event_type": "join", "participant_uuid": "p-1"}}
        )

    assert _spoken(policy) == [GREETING_TEXT]
    await policy.end_interview("test")
