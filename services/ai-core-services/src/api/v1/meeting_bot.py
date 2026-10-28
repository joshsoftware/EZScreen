from fastapi import APIRouter, status, Response

from src.core.logger import logger
from src.meeting_bot.client import bot_client
from src.meeting_bot.schemas import (
    AbortSessionRequest,
    AbortSessionResponse,
    BotStatusResponse,
    DeleteBotResponse,
    DispatchBotRequest,
    DispatchBotResponse,
    LeaveBotResponse,
)

router = APIRouter(prefix="/screening/bot", tags=["Meeting Bot Service"])


@router.post("/dispatch", response_model=DispatchBotResponse, status_code=status.HTTP_200_OK)
async def dispatch_bot(request: DispatchBotRequest):
    """Schedule an Attendee meeting bot for the specified interview session."""
    try:
        return await bot_client.dispatch_bot(request)
    except Exception as err:
        logger.error(
            "Bot dispatch failed",
            extra={"interview_session_id": request.interview_session_id, "error": str(err)},
        )
        return DispatchBotResponse(
            interview_session_id=request.interview_session_id,
            status="error",
            error_message=str(err),
        )


@router.post("/abort", response_model=AbortSessionResponse, status_code=status.HTTP_200_OK)
async def abort_session(request: AbortSessionRequest):
    """Stop a live interview without saving it and take its bot out of the
    meeting. core-api calls this when HR reschedules a session whose bot is
    already in the meeting but nothing has been answered yet."""
    from src.screening_pipeline.audio_websocket import active_sessions

    runtime = active_sessions.get(request.interview_session_id)
    if runtime is not None:
        await runtime.policy.abort_for_reschedule()
    if request.bot_id:
        # Best effort: the aborted runtime can no longer write to the session,
        # and a bot that already left (stale "in progress") can't leave again.
        left = await bot_client.leave_bot(request.bot_id)
        if left.status == "error":
            logger.warning(
                "Bot did not leave after abort",
                extra={"bot_id": request.bot_id, "error": left.error_message},
            )
    return AbortSessionResponse(interview_session_id=request.interview_session_id)


@router.get("/{bot_id}", response_model=BotStatusResponse, status_code=status.HTTP_200_OK)
async def get_bot_status(bot_id: str):
    """Fetch status of a dispatched meeting bot."""
    try:
        return await bot_client.get_bot_status(bot_id)
    except Exception as err:
        return BotStatusResponse(
            bot_id=bot_id,
            status="error",
            error_message=str(err),
        )


@router.post("/{bot_id}/leave", response_model=LeaveBotResponse, status_code=status.HTTP_200_OK)
async def leave_bot(bot_id: str):
    """Instruct the meeting bot to gracefully leave the meeting."""
    try:
        return await bot_client.leave_bot(bot_id)
    except Exception as err:
        return LeaveBotResponse(
            bot_id=bot_id,
            status="error",
            error_message=str(err),
        )


@router.delete(
    "/{bot_id}",
    response_model=None,
    responses={
        204: {"description": "Bot deleted"},
        200: {"model": DeleteBotResponse, "description": "Delete failed"},
    },
)
async def delete_bot(bot_id: str):
    """Delete a bot record from Attendee. Success is 204; domain failures return JSON."""
    try:
        success = await bot_client.delete_bot(bot_id)
        if not success:
            return DeleteBotResponse(
                bot_id=bot_id,
                status="error",
                error_message="Failed to delete bot",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as err:
        return DeleteBotResponse(
            bot_id=bot_id,
            status="error",
            error_message=str(err),
        )
