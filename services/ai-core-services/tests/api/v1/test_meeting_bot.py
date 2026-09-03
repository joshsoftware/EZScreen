from unittest.mock import AsyncMock, patch

import pytest

from src.meeting_bot.schemas import (
    BotStatusResponse,
    DispatchBotResponse,
    LeaveBotResponse,
)


@pytest.mark.asyncio
async def test_dispatch_bot_success(client):
    mock = DispatchBotResponse(
        bot_id="bot-1",
        interview_session_id="sess-1",
        status="scheduled",
        meeting_url="https://meet.google.com/abc",
        dispatched_at="2026-01-01T00:00:00+00:00",
    )
    with patch(
        "src.api.v1.meeting_bot.bot_client.dispatch_bot",
        new_callable=AsyncMock,
        return_value=mock,
    ):
        response = await client.post(
            "/screening/bot/dispatch",
            json={"interview_session_id": "sess-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["bot_id"] == "bot-1"


@pytest.mark.asyncio
async def test_dispatch_bot_returns_structured_error(client):
    with patch(
        "src.api.v1.meeting_bot.bot_client.dispatch_bot",
        new_callable=AsyncMock,
        side_effect=ValueError("Cannot dispatch bot. The scheduled interview time is in the past."),
    ):
        response = await client.post(
            "/screening/bot/dispatch",
            json={"interview_session_id": "sess-2"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "past" in body["error_message"]


@pytest.mark.asyncio
async def test_get_bot_status_success(client):
    mock = BotStatusResponse(
        bot_id="bot-1",
        status="ready",
        meeting_url="https://meet.google.com/abc",
        duration_seconds=10,
    )
    with patch(
        "src.api.v1.meeting_bot.bot_client.get_bot_status",
        new_callable=AsyncMock,
        return_value=mock,
    ):
        response = await client.get("/screening/bot/bot-1")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_leave_bot_error_body(client):
    with patch(
        "src.api.v1.meeting_bot.bot_client.leave_bot",
        new_callable=AsyncMock,
        side_effect=RuntimeError("attendee down"),
    ):
        response = await client.post("/screening/bot/bot-1/leave")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "attendee down" in body["error_message"]


@pytest.mark.asyncio
async def test_delete_bot_success_204(client):
    with patch(
        "src.api.v1.meeting_bot.bot_client.delete_bot",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = await client.delete("/screening/bot/bot-1")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_bot_failure_structured(client):
    with patch(
        "src.api.v1.meeting_bot.bot_client.delete_bot",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = await client.delete("/screening/bot/bot-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["bot_id"] == "bot-1"
