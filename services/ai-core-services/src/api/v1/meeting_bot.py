from fastapi import APIRouter, HTTPException, status
from src.meeting_bot.schemas import DispatchBotRequest, DispatchBotResponse, BotStatusResponse
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
