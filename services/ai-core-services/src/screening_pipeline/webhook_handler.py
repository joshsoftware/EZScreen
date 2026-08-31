import httpx
from fastapi import APIRouter, Request, status, BackgroundTasks
from typing import Dict, Any
from src.core.logger import logger
from src.core.config import settings
from src.meeting_bot.repository import interview_session_repo

router = APIRouter(tags=["Attendee Webhooks"])

async def update_session_status(session_id: str, new_status: str):
    """Make an internal API call to core-api to update session status."""
    try:
        # Assuming core-api is listening at settings.core_api_url
        url = f"{settings.core_api_url.rstrip('/')}/api/v1/interview-sessions/{session_id}/status"
        payload = {"status": new_status}
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.patch(url, json=payload)
            if resp.status_code not in (200, 204):
                logger.error("Failed to update status via core-api", extra={"status_code": resp.status_code, "body": resp.text})
    except Exception as err:
        logger.error("Error calling core-api for status update", extra={"error": str(err)})

async def process_state_change(payload: Dict[str, Any]):
    """Background task to handle bot state changes."""
    data = payload.get("data", {})
    bot_id = data.get("bot_id")
    new_state = data.get("state")

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
        # Bot left the meeting or it concluded
        await update_session_status(session.id, "completed")
        # TODO: Trigger final LLM summary & store to interview_analysis
        pass
        
    elif new_state == "fatal_error":
        # Bot crashed or failed to join
        await update_session_status(session.id, "failed")


async def process_participant_event(payload: Dict[str, Any]):
    """Background task to handle participant events (like barge-in)."""
    data = payload.get("data", {})
    bot_id = data.get("bot_id")
    event = data.get("event")
    
    if event == "speech_started":
        # TODO: Signal the TTS engine / orchestrator to STOP speaking (barge-in)
        logger.debug("Barge-in detected via webhook", extra={"bot_id": bot_id})


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
            
        elif trigger == "participant_events.speech_start_stop":
            background_tasks.add_task(process_participant_event, payload)
            
        else:
            logger.debug("Ignored webhook trigger", extra={"trigger": trigger})
            
    except Exception as err:
        logger.error("Error parsing webhook", extra={"error": str(err)})
        
    return {"status": "received"}
