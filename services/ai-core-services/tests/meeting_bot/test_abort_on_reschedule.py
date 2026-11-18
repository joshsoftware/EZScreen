"""Rescheduling takes the old booking's bot away.

On 14 Nov two bots from rescheduled screenings still joined their old
meetings at the old time and ran ~4 hours each on Attendee credits, because
only a bot already in a live interview was removed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.v1.meeting_bot import abort_session
from src.meeting_bot.schemas import AbortSessionRequest, LeaveBotResponse

CLIENT = "src.api.v1.meeting_bot.bot_client"


def _request():
    return AbortSessionRequest(interview_session_id="sess-1", bot_id="bot-old")


@pytest.mark.asyncio
async def test_a_bot_that_has_not_joined_yet_is_cancelled():
    with patch(f"{CLIENT}.delete_bot", AsyncMock(return_value=True)) as delete, patch(
        f"{CLIENT}.leave_bot", AsyncMock()
    ) as leave, patch("src.screening_pipeline.audio_websocket.active_sessions", {}):
        result = await abort_session(_request())

    delete.assert_awaited_once_with("bot-old")
    leave.assert_not_awaited()
    assert result.status == "aborted"


@pytest.mark.asyncio
async def test_a_bot_already_in_the_meeting_is_told_to_leave():
    """Attendee only cancels scheduled bots; one already joining/joined leaves."""
    with patch(f"{CLIENT}.delete_bot", AsyncMock(return_value=False)), patch(
        f"{CLIENT}.leave_bot", AsyncMock(return_value=LeaveBotResponse(bot_id="bot-old"))
    ) as leave, patch("src.screening_pipeline.audio_websocket.active_sessions", {}):
        await abort_session(_request())

    leave.assert_awaited_once_with("bot-old")


@pytest.mark.asyncio
async def test_a_live_interview_is_stopped_and_its_bot_leaves():
    runtime = MagicMock()
    runtime.policy.abort_for_reschedule = AsyncMock()
    with patch(f"{CLIENT}.delete_bot", AsyncMock()) as delete, patch(
        f"{CLIENT}.leave_bot", AsyncMock(return_value=LeaveBotResponse(bot_id="bot-old"))
    ) as leave, patch("src.screening_pipeline.audio_websocket.active_sessions", {"sess-1": runtime}):
        await abort_session(_request())

    runtime.policy.abort_for_reschedule.assert_awaited_once()
    delete.assert_not_awaited()  # it's in the meeting: no cancelling, it leaves
    leave.assert_awaited_once_with("bot-old")
