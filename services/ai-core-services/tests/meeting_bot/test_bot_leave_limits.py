"""Every bot gets a time limit and treats note-takers as bots.

On 14 Nov two forgotten bots stayed ~4 hours: Attendee only makes a bot
leave when it is alone, an AI note-taker ("Nikhil's Assistant") stayed in
the meeting, and bots had no maximum running time.
"""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.meeting_bot.client import AttendeeBotClient, NOTE_TAKER_KEYWORDS, automatic_leave_settings
from src.meeting_bot.schemas import AttendeeScheduleBotResponse, DispatchBotRequest


def _attendee_words(name):
    # Attendee splits display names on spaces, hyphens and underscores.
    return [w.lower() for w in re.split(r"[\s\-_]+", name) if w]


def test_max_running_time_is_the_booked_time_plus_25_minutes():
    assert automatic_leave_settings(30)["max_uptime_seconds"] == 55 * 60
    assert automatic_leave_settings(60)["max_uptime_seconds"] == 85 * 60
    assert automatic_leave_settings(None)["max_uptime_seconds"] == 55 * 60  # default 30 min


def test_note_takers_count_as_bots_but_people_do_not():
    keywords = set(automatic_leave_settings(30)["bot_keywords"])
    for name in ["Nikhil's Assistant", "Fireflies.ai Notetaker", "Otter.ai", "Read.ai meeting notes", "Fathom"]:
        assert keywords & set(_attendee_words(name)), name
    for name in ["Manasi Mane", "Nikhil Gosavi", "Pooja Sharma"]:
        assert not keywords & set(_attendee_words(name)), name
    assert all(not re.search(r"[\s\-_]", k) for k in NOTE_TAKER_KEYWORDS)  # whole words only


@pytest.mark.asyncio
async def test_every_dispatched_bot_carries_the_leave_settings():
    sent = {}

    async def fake_schedule(request):
        sent["req"] = request
        return AttendeeScheduleBotResponse(id="bot-1", status="scheduled", meeting_url="https://meet.google.com/x")

    session = SimpleNamespace(
        scheduled_at=None, interview_metadata={"duration_minutes": 45, "gmeet_link": "https://meet.google.com/x"},
        comment=None, generated_questions=[], application_id=None,
    )
    with patch("src.meeting_bot.client.interview_session_repo.get_by_id", AsyncMock(return_value=session)), patch(
        "src.meeting_bot.client.attendee_client.schedule_bot", side_effect=fake_schedule
    ), patch("src.meeting_bot.client.bot_connection_watchdog"), patch("src.meeting_bot.client.tts_prewarm_registry"):
        await AttendeeBotClient().dispatch_bot(DispatchBotRequest(interview_session_id="s1"))

    payload = sent["req"].model_dump(exclude_none=True)
    assert payload["automatic_leave_settings"]["max_uptime_seconds"] == 70 * 60
    assert "assistant" in payload["automatic_leave_settings"]["bot_keywords"]
