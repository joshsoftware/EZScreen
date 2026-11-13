import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import asyncio
import json
from src.core.logger import logger

router = APIRouter(tags=["Attendee WebSocket"])

# We will manage active sessions here
active_sessions: Dict[str, Any] = {}
seen_triggers = set()


# States in which the bot is waiting for, or working on, the candidate's reply.
_CANDIDATE_TURN_STATES = frozenset(
    # waiting_for_candidate: speech means the candidate is here (in case the
    # join webhook was missed).
    {"waiting_for_candidate", "listening", "collecting_answer", "evaluating", "closing"}
)


def _should_forward_candidate_audio(
    trigger: str | None,
    interaction_state: str,
    has_user_audio_stream: bool,
    bot_audible: bool = False,
) -> bool:
    """Select user audio, with mixed audio as Attendee-version fallback."""
    if trigger == "realtime_audio.user":
        return True
    # Some Attendee sessions provide only realtime_audio.mixed, which also
    # carries the bot's own voice. Drop it only while that voice is playing.
    # It used to be dropped in every state but "listening"/"closing", so once
    # a candidate paused and their first sentence was transcribed
    # ("collecting_answer"), the rest of a long answer was never heard: the
    # bot evaluated a truncated answer and talked over them (Bug-042).
    # Once a user stream is observed it is always preferred.
    return (
        trigger == "realtime_audio.mixed"
        and not has_user_audio_stream
        and not bot_audible
        and interaction_state in _CANDIDATE_TURN_STATES
    )


def _runtime_failed(runtime_task: asyncio.Task) -> bool:
    return (
        runtime_task.done()
        and not runtime_task.cancelled()
        and runtime_task.exception() is not None
    )


async def _receive_unless_runtime_failed(
    websocket: WebSocket, runtime_task: asyncio.Task
) -> dict | None:
    """Next WebSocket message, or None once the Pipecat runtime has crashed.

    A crashed runtime can never speak, so the audio stream must stop instead of
    keeping a silent (muted) bot in the meeting.
    """
    if runtime_task.done():
        return None if _runtime_failed(runtime_task) else await websocket.receive()
    receive_task = asyncio.ensure_future(websocket.receive())
    await asyncio.wait(
        {receive_task, runtime_task}, return_when=asyncio.FIRST_COMPLETED
    )
    if receive_task.done():
        return receive_task.result()
    if _runtime_failed(runtime_task):
        receive_task.cancel()
        await asyncio.gather(receive_task, return_exceptions=True)
        return None
    return await receive_task


async def _drain_until_disconnect(websocket: WebSocket) -> None:
    """Read and discard messages until the client goes away."""
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
    except (WebSocketDisconnect, RuntimeError):
        return


async def _run_pipecat_session(websocket: WebSocket, session_id: str):
    """Run Pipecat behind the existing Attendee WebSocket contract."""
    from src.screening_pipeline.pipecat_runtime import PipecatInterviewRuntime

    existing = active_sessions.get(session_id)
    if existing is not None and existing.policy.is_active:
        # One interviewer per session: a second runtime would start with an
        # empty memory and could end the interview as "never spoke" over the
        # real result (Bugs 44-46). Keep the running one.
        logger.warning(
            "Second audio connection for a running interview; ignoring it",
            extra={"session_id": session_id},
        )
        await _drain_until_disconnect(websocket)
        return

    runtime = PipecatInterviewRuntime(websocket=websocket, session_id=session_id)
    active_sessions[session_id] = runtime
    runtime_task = asyncio.create_task(runtime.run())
    messages_received = 0
    has_user_audio_stream = False

    try:
        while True:
            raw_ws_message = await _receive_unless_runtime_failed(websocket, runtime_task)
            if raw_ws_message is None:
                logger.error(
                    "Pipecat runtime crashed; closing Attendee audio stream",
                    extra={"session_id": session_id},
                )
                try:
                    await websocket.close()
                except Exception:
                    pass
                break

            if raw_ws_message.get("type") == "websocket.disconnect":
                break

            if raw_ws_message.get("bytes"):
                # Binary frames are candidate-only in this transport.  Keep
                # accepting them while evaluation/TTS is in flight so a
                # resumed answer can interrupt stale bot work.
                if runtime.policy.is_active:
                    await runtime.push_audio(raw_ws_message["bytes"], 24000)
                continue

            text = raw_ws_message.get("text")
            if not text:
                continue

            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                continue

            trigger = message.get("trigger") or message.get("event") or message.get("type")
            data = message.get("data", {})
            if not isinstance(data, dict):
                continue

            if messages_received < 5:
                logger.info(
                    "DEBUG Pipecat WS message",
                    extra={"session_id": session_id, "trigger": trigger},
                )
                messages_received += 1

            if trigger == "realtime_audio.user":
                has_user_audio_stream = True

            interaction_state = runtime.policy.current_interaction_state
            output = getattr(runtime, "output", None)
            bot_audible = bool(output is not None and output.is_bot_audible())
            if not _should_forward_candidate_audio(
                trigger,
                interaction_state,
                has_user_audio_stream,
                bot_audible,
            ):
                continue

            chunk_b64 = data.get("chunk")
            if not chunk_b64:
                continue

            try:
                pcm_bytes = base64.b64decode(chunk_b64, validate=True)
            except (ValueError, TypeError):
                continue

            await runtime.push_audio(pcm_bytes, data.get("sample_rate", 24000))
    finally:
        # Clean up while still registered, so a webhook arriving meanwhile
        # reaches this (ending) runtime; then unregister only this runtime,
        # never one a newer connection registered under the same session.
        await runtime.cleanup()
        if active_sessions.get(session_id) is runtime:
            active_sessions.pop(session_id, None)
        if not runtime_task.done():
            runtime_task.cancel()
        try:
            await runtime_task
        except asyncio.CancelledError:
            pass
        except Exception:
            # Already logged and handled (session failed, bot removed) by the runtime.
            pass

@router.websocket("/attendee-websocket/video/{session_id}")
async def attendee_video_ws(websocket: WebSocket, session_id: str):
    """Per-participant webcam frames from Attendee.

    Used only to tell whose camera is on before the interview starts; the
    pictures themselves are not decoded or stored.
    """
    from src.screening_pipeline.candidate_presence import record_webcam_frame

    await websocket.accept()
    logger.info("Attendee connected the video WebSocket", extra={"session_id": session_id})
    try:
        while True:
            raw = await websocket.receive()
            if raw.get("type") == "websocket.disconnect":
                break
            text = raw.get("text")
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                continue
            data = message.get("data") if isinstance(message, dict) else None
            if not isinstance(data, dict) or data.get("source") != "webcam":
                continue
            participant_uuid = data.get("participant_uuid")
            if not participant_uuid:
                continue
            if record_webcam_frame(session_id, participant_uuid):
                logger.info(
                    "Participant camera is on",
                    extra={"session_id": session_id, "participant_uuid": participant_uuid},
                )
                runtime = active_sessions.get(session_id)
                if runtime:
                    await runtime.policy.camera_frame_seen()
    except WebSocketDisconnect:
        pass


@router.websocket("/attendee-websocket/{session_id}")
async def attendee_audio_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for bidirectional audio streaming.
    Attendee will connect to this URL.
    """
    await websocket.accept()
    logger.info("Attendee connected to WebSocket", extra={"session_id": session_id})
    from src.meeting_bot.connection_watchdog import bot_connection_watchdog

    bot_connection_watchdog.mark_connected(session_id)

    await _run_pipecat_session(websocket, session_id)
