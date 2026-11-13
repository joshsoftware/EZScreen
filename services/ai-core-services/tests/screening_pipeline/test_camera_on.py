"""Start the interview only when the candidate's camera is on.

Attendee streams each participant's webcam frames (2 a second) to our video
WebSocket; the camera counts as on while the candidate's frames keep coming.
SCREENING_REQUIRE_CAMERA_ON switches the check off.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.screening_pipeline import candidate_presence as cp
from src.screening_pipeline.prompts import (
    CAMERA_PROMPT_TEXT,
    GREETING_TEXT,
    camera_not_on_note,
)
from tests.screening_pipeline.test_candidate_join_wait import _join, _policy, _spoken, _start

SID = "sess-join"


@pytest.fixture(autouse=True)
def _camera_check_on(monkeypatch):
    monkeypatch.setattr("src.core.config.settings.screening_require_camera_on", True)
    # One reminder per test is enough; don't wait 30 s for the next.
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.CAMERA_PROMPT_INTERVAL_SECONDS", 3600)
    cp.forget_session(SID)
    yield
    cp.forget_session(SID)


def _person(uuid, *, candidate=False, host=False, bot=False):
    cp.record_participant(SID, uuid, name=uuid, is_host=host, is_bot=bot, is_candidate=candidate)


# --- whose camera counts ---

def test_camera_check_is_on_by_default():
    from src.core.config import Settings

    assert Settings.model_fields["screening_require_camera_on"].default is True


def test_only_the_candidates_own_camera_counts():
    _person("cand", candidate=True)
    _person("hr", host=True)
    cp.record_webcam_frame(SID, "hr", now=100.0)
    assert not cp.candidate_camera_on(SID, now=100.0)  # HR's camera doesn't count

    cp.record_webcam_frame(SID, "cand", now=100.0)
    assert cp.candidate_camera_on(SID, now=101.0)


def test_camera_counts_as_off_once_frames_stop():
    _person("cand", candidate=True)
    cp.record_webcam_frame(SID, "cand", now=100.0)
    assert cp.candidate_camera_on(SID, now=104.0)
    assert not cp.candidate_camera_on(SID, now=106.0)  # no frame for over 5 s


def test_nickname_candidate_alone_with_the_host_counts():
    _person("hr", host=True)
    _person("nick")  # name didn't match, but the only non-host person
    cp.record_webcam_frame(SID, "nick", now=100.0)
    assert cp.candidate_camera_on(SID, now=100.0)


def test_leaving_clears_the_camera():
    _person("cand", candidate=True)
    cp.record_webcam_frame(SID, "cand", now=100.0)
    cp.remove_participant(SID, "cand")
    assert not cp.candidate_camera_on(SID, now=100.0)


def test_switched_off_the_camera_never_blocks(monkeypatch):
    monkeypatch.setattr("src.core.config.settings.screening_require_camera_on", False)
    _person("cand", candidate=True)
    assert cp.candidate_camera_on(SID)


# --- what the bot does ---

@pytest.mark.asyncio
async def test_candidate_with_camera_off_is_asked_to_turn_it_on():
    policy = _policy()
    await _start(policy)

    await _join(policy, {"participant_uuid": "c", "participant_name": "Pooja Sharma"})
    await asyncio.sleep(0)

    assert _spoken(policy) == [CAMERA_PROMPT_TEXT]
    assert policy.current_interaction_state == "waiting_for_candidate"

    # The camera comes on: the interview starts.
    cp.record_webcam_frame(SID, "c")
    await policy.camera_frame_seen()

    assert _spoken(policy)[:2] == [CAMERA_PROMPT_TEXT, GREETING_TEXT]
    assert policy._camera_prompt_task is None  # reminders stopped
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_camera_already_on_when_the_candidate_joins_starts_at_once():
    policy = _policy()
    await _start(policy)
    cp.record_webcam_frame(SID, "c")

    await _join(policy, {"participant_uuid": "c", "participant_name": "Pooja Sharma"})

    assert _spoken(policy)[:1] == [GREETING_TEXT]
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_hr_camera_does_not_start_it():
    policy = _policy()
    await _start(policy)
    await _join(policy, {"participant_uuid": "hr", "participant_name": "Rahul HR", "participant_is_host": True})
    await _join(policy, {"participant_uuid": "c", "participant_name": "Pooja Sharma"})
    cp.record_webcam_frame(SID, "hr")
    await policy.camera_frame_seen()
    await asyncio.sleep(0)

    assert GREETING_TEXT not in _spoken(policy)
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_camera_still_off_after_the_wait_is_a_no_show_with_its_own_note(monkeypatch):
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.CANDIDATE_JOIN_WAIT_SECONDS", 0)
    policy = _policy()
    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()):
        await _start(policy)
        await _join(policy, {"participant_uuid": "c", "participant_name": "Pooja Sharma"})
        if policy._candidate_wait_task is not None:
            await policy._candidate_wait_task

    assert GREETING_TEXT not in _spoken(policy)
    policy.api_client.update_status.assert_awaited_once_with("no_show", note=camera_not_on_note(0))
    policy._leave_bot_after_close.assert_awaited_once()
    assert policy._camera_prompt_task is None


@pytest.mark.asyncio
async def test_switched_off_the_interview_starts_without_a_camera(monkeypatch):
    monkeypatch.setattr("src.core.config.settings.screening_require_camera_on", False)
    policy = _policy()
    await _start(policy)

    await _join(policy, {"participant_uuid": "c", "participant_name": "Pooja Sharma"})

    assert _spoken(policy)[:1] == [GREETING_TEXT]
    await policy.end_interview("test")


# --- the Attendee request and the video connection ---

@pytest.mark.asyncio
async def test_bot_asks_attendee_for_webcam_frames_only_when_the_check_is_on(monkeypatch):
    from src.meeting_bot.client import AttendeeBotClient
    from src.meeting_bot.schemas import AttendeeScheduleBotResponse, DispatchBotRequest

    sent = {}

    async def fake_schedule(request):
        sent["req"] = request
        return AttendeeScheduleBotResponse(id="bot-1", status="scheduled", meeting_url="https://meet.google.com/x")

    dispatch = DispatchBotRequest(interview_session_id="s1", meeting_url="https://meet.google.com/x")
    with patch("src.meeting_bot.client.interview_session_repo.get_by_id", AsyncMock(return_value=None)), patch(
        "src.meeting_bot.client.attendee_client.schedule_bot", side_effect=fake_schedule
    ), patch("src.meeting_bot.client.bot_connection_watchdog"):
        await AttendeeBotClient().dispatch_bot(dispatch)
        video = sent["req"].websocket_settings.per_participant_video
        assert video is not None and video.url.endswith("/video/s1")
        assert video.webcam_resolution == "360p" and video.screenshare_resolution == "none"
        # Gallery view, so the candidate's tile is rendered even while others talk.
        assert sent["req"].recording_settings == {"format": "mp4", "view": "gallery_view"}

        monkeypatch.setattr("src.core.config.settings.screening_require_camera_on", False)
        await AttendeeBotClient().dispatch_bot(dispatch)
        assert sent["req"].websocket_settings.per_participant_video is None
        assert sent["req"].recording_settings == {"format": "mp4"}  # recordings as before
        payload = sent["req"].model_dump(exclude_none=True)
        assert "per_participant_video" not in payload["websocket_settings"]


def test_video_websocket_records_webcam_frames_and_ignores_screenshare():
    from src.screening_pipeline.audio_websocket import router

    app = FastAPI()
    app.include_router(router)
    runtime = MagicMock()
    runtime.policy.camera_frame_seen = AsyncMock()

    def frame(uuid, source):
        return json.dumps({
            "trigger": "realtime_video.per_participant",
            "data": {"frame": "...", "format": "jpeg", "participant_uuid": uuid, "source": source},
        })

    with patch("src.screening_pipeline.audio_websocket.active_sessions", {SID: runtime}):
        with TestClient(app).websocket_connect(f"/attendee-websocket/video/{SID}") as ws:
            ws.send_text(frame("s", "screenshare"))
            ws.send_text(frame("c", "webcam"))
            ws.send_text(frame("c", "webcam"))

    assert "c" in cp._webcam_seen_at[SID] and "s" not in cp._webcam_seen_at[SID]
    runtime.policy.camera_frame_seen.assert_awaited_once()  # only when the camera comes on
