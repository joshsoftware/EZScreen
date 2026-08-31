from fastapi import APIRouter, HTTPException, status, Response
from src.meeting_bot.schemas import DispatchBotRequest, DispatchBotResponse, BotStatusResponse, LeaveBotResponse
from src.meeting_bot.client import bot_client

router = APIRouter(prefix="/screening/bot", tags=["Meeting Bot Service"])


@router.post("/dispatch", response_model=DispatchBotResponse, status_code=status.HTTP_200_OK)
async def dispatch_bot(request: DispatchBotRequest):
    """Schedule an Attendee meeting bot for the specified interview session."""
    try:
        return await bot_client.dispatch_bot(request)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch meeting bot: {str(err)}"
        )


@router.get("/{bot_id}", response_model=BotStatusResponse, status_code=status.HTTP_200_OK)
async def get_bot_status(bot_id: str):
    """Fetch status of a dispatched meeting bot."""
    try:
        return await bot_client.get_bot_status(bot_id)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bot status: {str(err)}"
        )


@router.post("/{bot_id}/leave", response_model=LeaveBotResponse, status_code=status.HTTP_200_OK)
async def leave_bot(bot_id: str):
    """Instruct the meeting bot to gracefully leave the meeting."""
    try:
        return await bot_client.leave_bot(bot_id)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to instruct bot to leave: {str(err)}"
        )


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: str):
    """Delete a bot record from Attendee."""
    try:
        success = await bot_client.delete_bot(bot_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete bot"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete bot: {str(err)}"
        )
