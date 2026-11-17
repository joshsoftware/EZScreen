from typing import Any
from datetime import datetime, timezone
from src.core.logger import logger
from src.core.config import settings
from src.meeting_bot.repository import interview_session_repo
from src.meeting_bot.attendee import attendee_client
from src.meeting_bot.connection_watchdog import bot_connection_watchdog
from src.screening_pipeline.prompts import build_greeting
from src.screening_pipeline.tts_prewarm import coerce_questions_list, tts_prewarm_registry
from src.meeting_bot.schemas import (
    AttendeeAudioSettings,
    AttendeeWebsocketSettings,
    AttendeeScheduleBotRequest,
    DispatchBotRequest,
    DispatchBotResponse,
    BotStatusResponse,
    LeaveBotResponse,
)


# Attendee keeps a bot in the meeting until it is alone, and by default has no
# time limit. On 14 Nov two forgotten bots stayed ~4 hours because an AI
# note-taker ("Nikhil's Assistant") sat in the meeting. So every bot gets:
# * a maximum running time: the booked interview plus this many minutes
#   (Attendee starts the bot ~5 min early; then the wait for the candidate,
#   the interview, and the 1-2 minute overrun for the final question);
BOT_EXTRA_MINUTES = 25
DEFAULT_INTERVIEW_MINUTES = 30
# * note-taker / recorder names counted as bots, so our bot also leaves when
#   only bots are left. Attendee matches whole words in the display name.
NOTE_TAKER_KEYWORDS = [
    "assistant",
    "notetaker",
    "notetakers",
    "bot",
    "recorder",
    "otter.ai",
    "otter",
    "fireflies.ai",
    "fireflies",
    "fathom",
    "read.ai",
    "tldv",
    "tl;dv",
    "meetgeek",
    "transcriber",
]


def automatic_leave_settings(duration_minutes: Any) -> dict:
    minutes = (
        duration_minutes
        if isinstance(duration_minutes, (int, float)) and not isinstance(duration_minutes, bool) and duration_minutes > 0
        else DEFAULT_INTERVIEW_MINUTES
    )
    return {
        "max_uptime_seconds": int((minutes + BOT_EXTRA_MINUTES) * 60),
        "bot_keywords": NOTE_TAKER_KEYWORDS,
    }


class AttendeeBotClient:
    """Business logic coordinator for scheduling and querying Attendee meeting bots."""

    async def dispatch_bot(self, request: DispatchBotRequest) -> DispatchBotResponse:
        """Schedule an Attendee meeting bot for the specified interview session's scheduled_at time."""
        session_detail = await interview_session_repo.get_by_id(request.interview_session_id)

        meeting_url = request.meeting_url
        scheduled_at = None
        scheduled_at_dt: datetime | None = None
        if session_detail:
            scheduled_at = session_detail.scheduled_at
            if scheduled_at:
                try:
                    dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))

                    if dt < datetime.now(timezone.utc):
                        raise ValueError(
                            "Cannot dispatch bot. The scheduled interview time is in the past."
                        )
                    scheduled_at_dt = dt
                    scheduled_at = dt.isoformat()
                except ValueError:
                    raise
                except Exception as e:
                    logger.warning(f"Failed to parse scheduled_at: {e}")

            if not meeting_url:
                meta = session_detail.interview_metadata
                if isinstance(meta, dict):
                    link = meta.get("gmeet_link")
                    if isinstance(link, str) and link.strip():
                        meeting_url = link.strip()
            if not meeting_url and getattr(session_detail, "comment", None):
                meeting_url = session_detail.comment

        if not meeting_url:
            meeting_url = "https://meet.google.com/ezs-screener-demo"

        session_meta = getattr(session_detail, "interview_metadata", None) if session_detail else None
        duration_minutes = (
            session_meta.get("duration_minutes") if isinstance(session_meta, dict) else None
        )
        attendee_req = AttendeeScheduleBotRequest(
            meeting_url=meeting_url,
            automatic_leave_settings=automatic_leave_settings(duration_minutes),
            bot_name="ezscreener",
            join_at=scheduled_at,
            transcription_settings={
                "meeting_closed_captions": {}
            },
            websocket_settings=AttendeeWebsocketSettings(
                audio=AttendeeAudioSettings(
                    url=f"{settings.websocket_url.rstrip('/')}/{request.interview_session_id}",
                    sample_rate=24000
                )
            )
        )

        attendee_res = await attendee_client.schedule_bot(attendee_req)
        dispatched_at = datetime.now(timezone.utc).isoformat()
        bot_connection_watchdog.watch(
            request.interview_session_id, attendee_res.id, scheduled_at_dt
        )

        if session_detail:
            # Fire-and-forget: warms this session's TTS cache ahead of the
            # bot actually joining, instead of only starting once Attendee's
            # WebSocket connects (see tts_prewarm.py for why). Never blocks
            # the dispatch response and never raises on failure.
            questions = coerce_questions_list(
                getattr(session_detail, "generated_questions", None)
            )
            application_id = getattr(session_detail, "application_id", None)
            intro = (
                await interview_session_repo.get_interview_intro(application_id)
                if application_id
                else None
            )
            tts_prewarm_registry.schedule(
                request.interview_session_id,
                questions,
                join_at=scheduled_at_dt,
                extra_texts=[build_greeting(**intro)] if intro else (),
            )

        return DispatchBotResponse(
            bot_id=attendee_res.id,
            interview_session_id=request.interview_session_id,
            status=attendee_res.status,
            meeting_url=attendee_res.meeting_url,
            scheduled_at=scheduled_at,
            dispatched_at=dispatched_at,
        )

    async def get_bot_status(self, bot_id: str) -> BotStatusResponse:
        """Fetch bot status from Attendee API via attendee_client."""
        attendee_res = await attendee_client.get_bot(bot_id)
        return BotStatusResponse(
            bot_id=attendee_res.id,
            status=attendee_res.status,
            meeting_url=attendee_res.meeting_url,
            duration_seconds=attendee_res.duration_seconds,
        )

    async def leave_bot(self, bot_id: str) -> LeaveBotResponse:
        """Instruct the bot to leave the meeting."""
        return await attendee_client.leave_bot(bot_id)

    async def delete_bot(self, bot_id: str) -> bool:
        """Delete the bot from Attendee."""
        return await attendee_client.delete_bot(bot_id)


bot_client = AttendeeBotClient()
