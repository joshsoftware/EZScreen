"""Remove a bot that joined the meeting but never connected its audio to ai-core.

Attendee opens the audio WebSocket to WEBSOCKET_URL once the bot joins. If that
URL is unreachable (tunnel down, wrong host), nothing in the screening pipeline
ever runs, so the bot sits in the meeting silently and shows as muted (Bug-043).
This watchdog runs inside ai-core and only makes outbound calls to Attendee, so
it still works when Attendee cannot reach ai-core.

Watches are in-memory: an ai-core restart drops pending ones.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.core.config import settings
from src.core.logger import logger
from src.meeting_bot.attendee import attendee_client

JOINED_STATES = frozenset(
    {"joined_recording", "joined_not_recording", "joined_recording_paused"}
)
FINISHED_STATES = frozenset(
    {"leaving", "post_processing", "ended", "fatal_error", "data_deleted"}
)


class BotConnectionWatchdog:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def watch(self, session_id: str, bot_id: str, join_at: datetime | None) -> None:
        """Start (or restart, on reschedule) the watch for a dispatched bot."""
        self.cancel(session_id)
        self._tasks[session_id] = asyncio.create_task(
            self._watch(session_id, bot_id, join_at)
        )

    def mark_connected(self, session_id: str) -> None:
        """Attendee's audio WebSocket arrived; the bot can talk."""
        self.cancel(session_id)

    def cancel(self, session_id: str) -> None:
        task = self._tasks.pop(session_id, None)
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()

    async def _watch(self, session_id: str, bot_id: str, join_at: datetime | None) -> None:
        loop = asyncio.get_running_loop()
        try:
            start = join_at or datetime.now(timezone.utc)
            wait = (start - datetime.now(timezone.utc)).total_seconds()
            await asyncio.sleep(max(wait, 0) + settings.screening_bot_connect_grace_seconds)
            deadline = loop.time() + settings.screening_bot_connect_max_wait_seconds
            while True:
                state = (await attendee_client.get_bot(bot_id)).status
                if state in FINISHED_STATES:
                    return
                if state in JOINED_STATES:
                    # Give a just-admitted bot time to open its WebSocket;
                    # mark_connected() cancels this task if it does.
                    await asyncio.sleep(settings.screening_bot_connect_confirm_seconds)
                    await self._remove_unconnected_bot(session_id, bot_id)
                    return
                if loop.time() >= deadline:
                    return
                await asyncio.sleep(settings.screening_bot_connect_poll_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Bot connection watchdog failed",
                extra={"session_id": session_id, "bot_id": bot_id},
            )
        finally:
            if self._tasks.get(session_id) is asyncio.current_task():
                self._tasks.pop(session_id, None)

    async def _remove_unconnected_bot(self, session_id: str, bot_id: str) -> None:
        from src.screening_pipeline.session_api import SessionApiClient

        logger.error(
            "Bot joined the meeting but its audio never reached ai-core; removing it. "
            "Check that WEBSOCKET_URL / the public tunnel is reachable.",
            extra={
                "session_id": session_id,
                "bot_id": bot_id,
                "websocket_url": settings.websocket_url,
            },
        )
        await SessionApiClient(session_id=session_id).update_status("failed")
        await attendee_client.leave_bot(bot_id)


bot_connection_watchdog = BotConnectionWatchdog()
