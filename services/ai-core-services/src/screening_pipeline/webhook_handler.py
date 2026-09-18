import httpx
from fastapi import APIRouter, Request, status, BackgroundTasks
from typing import Dict, Any
from src.core.logger import logger
from src.core.config import settings
from src.meeting_bot.repository import interview_session_repo

router = APIRouter(prefix="/screening", tags=["Attendee Webhooks"])

async def update_session_status(session_id: str, new_status: str):
    """Make an internal API call to core-api to update session status."""
    try:
        # Assuming core-api is listening at settings.core_api_url
        url = f"{settings.core_api_url.rstrip('/')}/api/v1/interview-sessions/{session_id}/status"
        payload = {"status": new_status}
        headers = {}
        if settings.internal_service_token:
            headers["X-Internal-Service-Token"] = settings.internal_service_token

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.patch(url, json=payload, headers=headers)
            if resp.status_code not in (200, 204):
                logger.error("Failed to update status via core-api", extra={"status_code": resp.status_code, "body": resp.text})
    except Exception as err:
        logger.error("Error calling core-api for status update", extra={"error": str(err)})

async def process_state_change(payload: Dict[str, Any]):
    """Background task to handle bot state changes."""
    data = payload.get("data", {})
    # Attendee sends bot_id at the payload root and the state as data.new_state.
    bot_id = payload.get("bot_id") or data.get("bot_id")
    new_state = data.get("new_state") or data.get("state")

    if not bot_id or not new_state:
        logger.warning("Webhook missing bot_id or state", extra={"payload": payload})
        return

    session = await interview_session_repo.get_by_bot_id(bot_id)
    if not session:
        logger.warning("Received webhook for unknown bot", extra={"bot_id": bot_id})
        return

    logger.info("Bot state changed", extra={"bot_id": bot_id, "new_state": new_state, "session_id": session.id})

    # State machine logic
    if new_state == "joined_recording":
        # Bot successfully entered the meeting
        await update_session_status(session.id, "in_progress")
        # TODO: Trigger orchestrator start sequence (greeting)
        pass
    
    elif new_state in ["ended", "left"]:
        # A live runtime owns the transcript and must finalize before this
        # confirmation webhook marks the session complete.  It is safe to
        # receive this after normal completion: end_interview is idempotent.
        from src.screening_pipeline.audio_websocket import active_sessions

        runtime = active_sessions.get(str(session.id))
        if runtime:
            await runtime.policy.end_interview("meeting_ended")
        await update_session_status(session.id, "completed")
        
    elif new_state == "fatal_error":
        # Bot crashed or failed to join
        await update_session_status(session.id, "failed")


async def process_participant_event(payload: Dict[str, Any]):
    """Handle barge-in plus provider participant/meeting end events."""
    data = payload.get("data", {})
    bot_id = data.get("bot_id") or payload.get("bot_id")
    event = str(data.get("event") or data.get("event_type") or "").lower()
    
    if event == "speech_started":
        # Live audio VAD performs the actual interruption; this remains useful
        # diagnostic coverage when provider webhook delivery races audio.
        logger.debug("Barge-in detected via webhook", extra={"bot_id": bot_id})

    # Provider event spelling varies by meeting platform, so accept the
    # canonical leave/end values without making a speech event terminal.
    if event not in {"participant_left", "participant_leave", "leave", "left", "meeting_ended"} or not bot_id:
        return

    session = await interview_session_repo.get_by_bot_id(bot_id)
    if not session:
        logger.warning("Participant event for unknown bot", extra={"bot_id": bot_id, "event": event})
        return

    # A meeting can include recruiters or observers.  Never terminate an
    # interview merely because an arbitrary participant left; the dispatch
    # metadata identifies the intended candidate when that signal is needed.
    metadata = getattr(session, "interview_metadata", None)
    candidate_uuid = metadata.get("candidate_participant_uuid") if isinstance(metadata, dict) else None
    participant_uuid = data.get("participant_uuid")
    if event != "meeting_ended" and (not candidate_uuid or candidate_uuid != participant_uuid):
        logger.info(
            "Ignored non-candidate participant leave",
            extra={"bot_id": bot_id, "participant_uuid": participant_uuid},
        )
        return

    from src.screening_pipeline.audio_websocket import active_sessions

    runtime = active_sessions.get(str(session.id))
    if runtime:
        await runtime.policy.end_interview("candidate_left")
    await update_session_status(session.id, "completed")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def handle_attendee_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives all lifecycle and participant events from Attendee.dev.
    Uses BackgroundTasks so Attendee gets an immediate 200 OK.
    """
    try:
        payload = await request.json()
        trigger = payload.get("trigger")
        
        if trigger == "bot.state_change":
            background_tasks.add_task(process_state_change, payload)
            
        elif trigger in {"participant_events.speech_start_stop", "participant_events.join_leave"}:
            background_tasks.add_task(process_participant_event, payload)
            
        else:
            logger.debug("Ignored webhook trigger", extra={"trigger": trigger})
            
    except Exception as err:
        logger.error("Error parsing webhook", extra={"error": str(err)})
        
    return {"status": "received"}
