import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.meeting_bot.attendee import AttendeeApiClient
from src.meeting_bot.connection_watchdog import BotConnectionWatchdog


@pytest.fixture(autouse=True)
def fast_watchdog(monkeypatch):
    for name in (
        "screening_bot_connect_grace_seconds",
        "screening_bot_connect_poll_seconds",
        "screening_bot_connect_confirm_seconds",
    ):
        monkeypatch.setattr(f"src.meeting_bot.connection_watchdog.settings.{name}", 0)
    monkeypatch.setattr(
        "src.meeting_bot.connection_watchdog.settings.screening_bot_connect_max_wait_seconds", 1
    )


def _attendee(*states):
    client = MagicMock()
    client.get_bot = AsyncMock(side_effect=[MagicMock(status=s) for s in states])
    client.leave_bot = AsyncMock()
    return client


async def _run(watchdog, session_id="session-id"):
    task = watchdog._tasks[session_id]
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=2)


@pytest.mark.asyncio
async def test_joined_bot_without_audio_connection_is_removed_and_session_failed():
    attendee = _attendee("joining", "joined_recording")
    api = MagicMock(update_status=AsyncMock(return_value=True))
    watchdog = BotConnectionWatchdog()
    with patch("src.meeting_bot.connection_watchdog.attendee_client", attendee), patch(
        "src.screening_pipeline.session_api.SessionApiClient", return_value=api
    ):
        watchdog.watch("session-id", "bot-1", None)
        await _run(watchdog)

    api.update_status.assert_awaited_once_with("failed")
    attendee.leave_bot.assert_awaited_once_with("bot-1")


@pytest.mark.asyncio
async def test_audio_connection_cancels_the_watch():
    attendee = _attendee("joined_recording")
    watchdog = BotConnectionWatchdog()
    with patch("src.meeting_bot.connection_watchdog.attendee_client", attendee):
        watchdog.watch("session-id", "bot-1", None)
        task = watchdog._tasks["session-id"]
        watchdog.mark_connected("session-id")
        await asyncio.gather(task, return_exceptions=True)

    assert task.cancelled()
    attendee.leave_bot.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_that_already_ended_is_left_alone():
    attendee = _attendee("fatal_error")
    watchdog = BotConnectionWatchdog()
    with patch("src.meeting_bot.connection_watchdog.attendee_client", attendee):
        watchdog.watch("session-id", "bot-1", None)
        await _run(watchdog)

    attendee.leave_bot.assert_not_awaited()


@pytest.mark.asyncio
async def test_rescheduling_replaces_the_previous_watch():
    attendee = _attendee("joined_recording")
    watchdog = BotConnectionWatchdog()
    with patch("src.meeting_bot.connection_watchdog.attendee_client", attendee):
        watchdog.watch("session-id", "old-bot", None)
        old = watchdog._tasks["session-id"]
        watchdog.watch("session-id", "new-bot", None)
        await asyncio.gather(old, return_exceptions=True)
        watchdog.cancel("session-id")

    assert old.cancelled()


@pytest.mark.asyncio
async def test_get_bot_reads_attendee_state_field(monkeypatch):
    client = AttendeeApiClient()
    client.api_key = "key"
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "id": "bot-1",
        "state": "joined_recording",
        "meeting_url": "https://meet.google.com/abc-defg-hij",
    }
    http = MagicMock()
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.get = AsyncMock(return_value=response)
    monkeypatch.setattr("src.meeting_bot.attendee.httpx.AsyncClient", lambda **_: http)

    bot = await client.get_bot("bot-1")

    assert bot.status == "joined_recording"
