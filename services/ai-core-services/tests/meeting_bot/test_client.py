from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.meeting_bot.client import AttendeeBotClient
from src.meeting_bot.schemas import AttendeeScheduleBotResponse, DispatchBotRequest


@pytest.mark.asyncio
async def test_dispatch_bot_rejects_past_schedule():
    # Calendar stores IST labeled as UTC; client subtracts 5h30m → past relative to now.
    session = SimpleNamespace(
        scheduled_at=datetime.now(timezone.utc).isoformat(),
        comment="https://meet.google.com/abc",
    )
    client = AttendeeBotClient()

    with patch(
        "src.meeting_bot.client.interview_session_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=session,
    ):
        with pytest.raises(ValueError, match="in the past"):
            await client.dispatch_bot(
                DispatchBotRequest(interview_session_id="sess-1")
            )


@pytest.mark.asyncio
async def test_dispatch_bot_schedules_a_tts_prewarm_with_the_session_questions_and_join_time():
    join_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    session = SimpleNamespace(
        scheduled_at=join_at.isoformat(),
        comment="https://meet.google.com/abc",
        interview_metadata=None,
        generated_questions=[{"question": "What is Docker?"}],
    )
    client = AttendeeBotClient()
    schedule_bot_response = AttendeeScheduleBotResponse(
        id="bot-1", status="scheduled", meeting_url="https://meet.google.com/abc"
    )

    with patch(
        "src.meeting_bot.client.interview_session_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "src.meeting_bot.client.attendee_client.schedule_bot",
        new_callable=AsyncMock,
        return_value=schedule_bot_response,
    ), patch(
        "src.meeting_bot.client.tts_prewarm_registry.schedule"
    ) as prewarm_schedule:
        await client.dispatch_bot(DispatchBotRequest(interview_session_id="sess-1"))

    prewarm_schedule.assert_called_once()
    call_args = prewarm_schedule.call_args
    assert call_args.args[0] == "sess-1"
    assert call_args.args[1] == [{"question": "What is Docker?"}]
    assert call_args.kwargs["join_at"] == join_at


@pytest.mark.asyncio
async def test_dispatch_bot_does_not_schedule_a_prewarm_when_session_is_missing():
    client = AttendeeBotClient()
    schedule_bot_response = AttendeeScheduleBotResponse(
        id="bot-1", status="scheduled", meeting_url="https://meet.google.com/abc"
    )

    with patch(
        "src.meeting_bot.client.interview_session_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "src.meeting_bot.client.attendee_client.schedule_bot",
        new_callable=AsyncMock,
        return_value=schedule_bot_response,
    ), patch(
        "src.meeting_bot.client.tts_prewarm_registry.schedule"
    ) as prewarm_schedule:
        await client.dispatch_bot(
            DispatchBotRequest(
                interview_session_id="sess-1",
                meeting_url="https://meet.google.com/abc",
            )
        )

    prewarm_schedule.assert_not_called()
