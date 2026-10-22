import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.storage import _ChunkReader
from src.meeting_bot.schemas import AttendeeScheduleBotRequest
from src.screening_pipeline import recording_import
from src.screening_pipeline.webhook_handler import process_state_change

KEY = "orgs/o/jobs/j/recordings/sess-1.mp4"


def test_bots_are_asked_to_record_mp4():
    payload = AttendeeScheduleBotRequest(meeting_url="https://meet.google.com/abc").model_dump(
        exclude_none=True
    )

    assert payload["recording_settings"] == {"format": "mp4"}


def test_chunk_reader_streams_chunks_as_a_file():
    reader = _ChunkReader(iter([b"abc", b"", b"defgh"]))

    assert reader.read(2) == b"ab"
    assert reader.read() == b"cdefgh"
    assert reader.read(4) == b""


@pytest.mark.asyncio
async def test_successful_copy_reports_the_key():
    with patch.object(
        recording_import.attendee_client, "get_recording_url", AsyncMock(return_value="https://x/rec.mp4")
    ), patch.object(recording_import, "_copy_to_minio") as copy, patch.object(
        recording_import, "_report", AsyncMock()
    ) as report:
        await recording_import.import_recording("sess-1", "bot-1", KEY)

    copy.assert_called_once_with("https://x/rec.mp4", KEY)
    report.assert_awaited_once_with("sess-1", {"success": True, "s3_key": KEY})


@pytest.mark.asyncio
async def test_recording_not_ready_is_reported_as_retryable():
    with patch.object(
        recording_import.attendee_client, "get_recording_url", AsyncMock(return_value=None)
    ), patch.object(recording_import, "_copy_to_minio") as copy, patch.object(
        recording_import, "_report", AsyncMock()
    ) as report:
        await recording_import.import_recording("sess-1", "bot-1", KEY)

    copy.assert_not_called()
    payload = report.await_args.args[1]
    assert payload["success"] is False and payload["retryable"] is True


@pytest.mark.asyncio
async def test_a_failed_report_never_raises():
    with patch.object(
        recording_import.attendee_client, "get_recording_url", AsyncMock(return_value="https://x")
    ), patch.object(recording_import, "_copy_to_minio"), patch.object(
        recording_import, "_report", AsyncMock(side_effect=RuntimeError("core-api down"))
    ):
        await recording_import.import_recording("sess-1", "bot-1", KEY)


@pytest.mark.asyncio
async def test_poller_copies_every_claimed_import(monkeypatch):
    monkeypatch.setattr(recording_import.settings, "recording_import_poll_seconds", 0)
    claimed = [{"interview_session_id": "sess-1", "bot_id": "bot-1", "s3_key": KEY}]
    claim = AsyncMock(side_effect=[claimed, []])
    with patch.object(recording_import, "_claim_due", claim), patch.object(
        recording_import, "import_recording", AsyncMock()
    ) as do_import:
        poller = asyncio.create_task(recording_import.run_recording_import_poller())
        for _ in range(50):
            if claim.await_count >= 2:
                break
            await asyncio.sleep(0.01)
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)

    do_import.assert_awaited_once_with("sess-1", "bot-1", KEY)


@pytest.mark.parametrize("state, scheduled", [("ended", True), ("left", False)])
@pytest.mark.asyncio
async def test_recording_copy_is_scheduled_only_once_the_bot_has_ended(state, scheduled):
    session = MagicMock()
    session.id = "sess-1"
    with patch(
        "src.screening_pipeline.webhook_handler.interview_session_repo.get_by_bot_id",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "src.screening_pipeline.webhook_handler.update_session_status",
        new_callable=AsyncMock,
    ), patch(
        "src.screening_pipeline.recording_import.schedule_recording_import",
        new_callable=AsyncMock,
    ) as schedule:
        await process_state_change({"bot_id": "bot-1", "data": {"new_state": state}})

    if scheduled:
        schedule.assert_awaited_once_with("sess-1", "bot-1")
    else:
        schedule.assert_not_awaited()
