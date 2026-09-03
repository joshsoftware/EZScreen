from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.meeting_bot.client import AttendeeBotClient
from src.meeting_bot.schemas import DispatchBotRequest


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
