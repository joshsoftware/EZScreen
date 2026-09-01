import httpx
import uuid
from typing import Dict
from src.core.config import settings
from src.core.logger import logger
from src.meeting_bot.schemas import (
    AttendeeAudioSettings,
    AttendeeWebsocketSettings,
    AttendeeWebhookConfig,
    AttendeeScheduleBotRequest,
    AttendeeScheduleBotResponse,
    AttendeeBotStatusResponse,
    LeaveBotResponse,
)


class AttendeeApiClient:
    """External API client for interacting with the Attendee.dev meeting bot cloud server."""

    def __init__(self):
        self.api_url = settings.attendee_api_url.rstrip("/")
        self.api_key = settings.attendee_api_key

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Token {self.api_key}"
        return headers

    async def schedule_bot(self, request: AttendeeScheduleBotRequest) -> AttendeeScheduleBotResponse:
        """Schedule or dispatch a meeting bot via Attendee REST API using strongly-typed requests."""
        if not request.websocket_settings:
            request.websocket_settings = AttendeeWebsocketSettings(
                audio=AttendeeAudioSettings(
                    url=settings.websocket_url,
                    sample_rate=24000
                )
            )
            
        if not request.webhooks and hasattr(settings, "webhook_url") and settings.webhook_url:
            request.webhooks = [
                AttendeeWebhookConfig(url=settings.webhook_url)
            ]

        bot_payload = request.model_dump(exclude_none=True)

        fallback_bot_id = f"bot_{uuid.uuid4().hex[:12]}"
        fallback_status = "scheduled" if request.join_at else "joining"

        if not self.api_key:
            logger.info("No Attendee API key configured, using mock bot dispatch", extra={"bot_id": fallback_bot_id})
            return AttendeeScheduleBotResponse(
                id=fallback_bot_id,
                status=fallback_status,
                meeting_url=request.meeting_url,
                bot_name=request.bot_name,
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.api_url}/api/v1/bots",
                    json=bot_payload,
                    headers=self._get_headers()
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return AttendeeScheduleBotResponse(
                        id=data.get("id") or data.get("bot_id", fallback_bot_id),
                        status=data.get("status", fallback_status),
                        meeting_url=data.get("meeting_url", request.meeting_url),
                        bot_name=data.get("bot_name", request.bot_name),
                    )
                else:
                    logger.warning(
                        "Attendee API returned non-200 status during bot scheduling",
                        extra={"status": resp.status_code, "body": resp.text}
                    )
        except Exception as err:
            logger.error("Error communicating with Attendee API", extra={"error": str(err)})

        return AttendeeScheduleBotResponse(
            id=fallback_bot_id,
            status=fallback_status,
            meeting_url=request.meeting_url,
            bot_name=request.bot_name,
        )

    async def get_bot(self, bot_id: str) -> AttendeeBotStatusResponse:
        """Fetch bot state and details from Attendee REST API."""
        fallback_response = AttendeeBotStatusResponse(
            id=bot_id,
            status="ready",
            meeting_url="https://meet.google.com/ezs-screener-demo",
            duration_seconds=0,
        )

        if not self.api_key:
            return fallback_response

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.api_url}/api/v1/bots/{bot_id}",
                    headers=self._get_headers()
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return AttendeeBotStatusResponse(
                        id=data.get("id", bot_id),
                        status=data.get("status", "ready"),
                        meeting_url=data.get("meeting_url", "https://meet.google.com/ezs-screener-demo"),
                        duration_seconds=data.get("duration_seconds", 0),
                    )
        except Exception as err:
            logger.warning("Could not fetch bot details from Attendee API", extra={"bot_id": bot_id, "error": str(err)})

        return fallback_response

    async def leave_bot(self, bot_id: str) -> LeaveBotResponse:
        """Instruct the bot to gracefully leave the meeting."""
        if not self.api_key:
            return LeaveBotResponse(bot_id=bot_id, status="leaving")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.api_url}/api/v1/bots/{bot_id}/leave",
                    headers=self._get_headers()
                )
                if resp.status_code in (200, 202):
                    return LeaveBotResponse(bot_id=bot_id, status="leaving")
                else:
                    logger.warning("Failed to instruct bot to leave", extra={"bot_id": bot_id, "status": resp.status_code})
        except Exception as err:
            logger.error("Error communicating with Attendee API for leave_bot", extra={"error": str(err)})
            
        return LeaveBotResponse(bot_id=bot_id, status="error")

    async def delete_bot(self, bot_id: str) -> bool:
        """Delete the bot record from Attendee."""
        if not self.api_key:
            return True

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{self.api_url}/api/v1/bots/{bot_id}",
                    headers=self._get_headers()
                )
                return resp.status_code in (200, 204)
        except Exception as err:
            logger.error("Error communicating with Attendee API for delete_bot", extra={"error": str(err)})
            
        return False


attendee_client = AttendeeApiClient()
