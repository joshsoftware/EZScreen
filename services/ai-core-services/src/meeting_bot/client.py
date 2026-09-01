from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from src.core.logger import logger
from src.core.config import settings
from src.meeting_bot.repository import interview_session_repo
from src.meeting_bot.attendee import attendee_client
from src.meeting_bot.schemas import (
    AttendeeAudioSettings,
    AttendeeWebsocketSettings,
    AttendeeScheduleBotRequest,
    DispatchBotRequest,
    DispatchBotResponse,
    BotStatusResponse,
    LeaveBotResponse,
)


class AttendeeBotClient:
    """Business logic coordinator for scheduling and querying Attendee meeting bots."""

    async def dispatch_bot(self, request: DispatchBotRequest) -> DispatchBotResponse:
        """Schedule an Attendee meeting bot for the specified interview session's scheduled_at time."""
        session_detail = await interview_session_repo.get_by_id(request.interview_session_id)
        
        meeting_url = request.meeting_url
        scheduled_at = None
        if session_detail:
            scheduled_at = session_detail.scheduled_at
            if scheduled_at:
                try:
                    # The calendar saves IST but marks it as UTC. 
                    # We subtract 5:30 to get the TRUE UTC time for Attendee.dev
                    dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
                    dt = dt - timedelta(hours=5, minutes=30)
                    
                    # If it's already past the start time, block it and return an error to the user
                    if dt < datetime.now(timezone.utc):
                        raise HTTPException(status_code=400, detail="Cannot dispatch bot. The scheduled interview time is in the past.")
                    else:
                        scheduled_at = dt.isoformat()
                except HTTPException:
                    raise # Re-raise the 400 error so Postman sees it
                except Exception as e:
                    logger.warning(f"Failed to adjust scheduled_at for IST: {e}")
                    
            if not meeting_url and session_detail.comment:
                meeting_url = session_detail.comment

        if not meeting_url:
            meeting_url = "https://meet.google.com/ezs-screener-demo"

        # Construct strongly-typed AttendeeScheduleBotRequest
        attendee_req = AttendeeScheduleBotRequest(
            meeting_url=meeting_url,
            bot_name="ezscreener",
            join_at=scheduled_at,
            transcription_settings={
                "meeting_closed_captions": {}
            },
            websocket_settings=AttendeeWebsocketSettings(
                audio=AttendeeAudioSettings(
                    url=f"{settings.websocket_url.rstrip('/')}/{request.interview_session_id}",
                    sample_rate=24000,
                    receive_audio=True,
                    listen=True,
                    events=["realtime_audio.mixed"]
                )
            )
        )

        # Execute external Attendee API call using typed request & response
        attendee_res = await attendee_client.schedule_bot(attendee_req)

        dispatched_at = datetime.now(timezone.utc).isoformat()
        
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
