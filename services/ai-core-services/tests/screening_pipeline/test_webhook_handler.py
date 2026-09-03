from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.webhook_handler import process_state_change


@pytest.mark.asyncio
async def test_process_state_change_marks_in_progress_on_joined():
    session = MagicMock()
    session.id = "sess-1"

    with patch(
        "src.screening_pipeline.webhook_handler.interview_session_repo.get_by_bot_id",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "src.screening_pipeline.webhook_handler.update_session_status",
        new_callable=AsyncMock,
    ) as mock_update:
        await process_state_change(
            {"data": {"bot_id": "bot-1", "state": "joined_recording"}}
        )

    mock_update.assert_awaited_once_with("sess-1", "in_progress")


@pytest.mark.asyncio
async def test_process_state_change_ignores_unknown_bot():
    with patch(
        "src.screening_pipeline.webhook_handler.interview_session_repo.get_by_bot_id",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "src.screening_pipeline.webhook_handler.update_session_status",
        new_callable=AsyncMock,
    ) as mock_update:
        await process_state_change({"data": {"bot_id": "missing", "state": "ended"}})

    mock_update.assert_not_awaited()
