import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
from src.core.logger import logger

router = APIRouter(tags=["Attendee WebSocket"])

# We will manage active sessions here
active_sessions: Dict[str, Any] = {}
seen_triggers = set()

async def speak_to_attendee(websocket: WebSocket, pcm_bytes: bytes):
    """Utility to chunk and send PCM audio to Attendee."""
    # Chunk PCM bytes into 2400-byte frames (50ms at 24kHz)
    chunk_size = 2400
    for i in range(0, len(pcm_bytes), chunk_size):
        chunk = pcm_bytes[i:i + chunk_size]
        await websocket.send_json({
            "trigger": "realtime_audio.bot_output",
            "data": {
                "chunk": base64.b64encode(chunk).decode('utf-8'),
                "sample_rate": 24000
            }
        })

@router.websocket("/attendee-websocket/{session_id}")
async def attendee_audio_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for bidirectional audio streaming.
    Attendee will connect to this URL.
    """
    await websocket.accept()
    logger.info("Attendee connected to WebSocket", extra={"session_id": session_id})
    
    from src.screening_pipeline.orchestrator import InterviewOrchestrator
    orchestrator = InterviewOrchestrator(session_id=session_id, websocket=websocket)
    active_sessions[session_id] = orchestrator
    
    logger.info("Bot audio stream initialized", extra={"session_id": session_id})
    
    import asyncio
    asyncio.create_task(orchestrator.start())
    
    messages_received = 0
    try:
        while True:
            raw_ws_message = await websocket.receive()
            
            if raw_ws_message.get("type") == "websocket.disconnect":
                logger.info("Attendee WebSocket disconnected gracefully (ASGI disconnect)")
                break
                
            if "bytes" in raw_ws_message and raw_ws_message["bytes"]:
                pcm_bytes = raw_ws_message["bytes"]
                if messages_received < 5:
                    logger.info(f"DEBUG Raw WS BINARY Frame #{messages_received}: size {len(pcm_bytes)} bytes")
                    messages_received += 1
                
                # If it's a raw binary frame, it's almost certainly the audio stream!
                # We assume 24000 sample rate for raw inbound PCM.
                if session_id in active_sessions:
                    await orchestrator.stt_client.send_audio(pcm_bytes, 24000)
                continue
            
            if "text" not in raw_ws_message or not raw_ws_message["text"]:
                continue
                
            import json
            try:
                message = json.loads(raw_ws_message["text"])
            except json.JSONDecodeError:
                continue
            
            # Debug log the first 5 incoming messages to inspect their exact structure
            if messages_received < 5:
                # Omit base64 chunk to avoid massive logs
                debug_msg = {k: v for k, v in message.items() if k != "data"}
                if "data" in message and isinstance(message["data"], dict):
                    debug_msg["data_keys"] = list(message["data"].keys())
                    if "sample_rate" in message["data"]:
                        debug_msg["sample_rate"] = message["data"]["sample_rate"]
                logger.info(f"DEBUG Raw WS TEXT Message #{messages_received}: {debug_msg}")
                messages_received += 1
                
            # Attendee might use "event", "type", or "trigger" depending on API version
            trigger = message.get("trigger") or message.get("event") or message.get("type")
            data = message.get("data", {})
            
            if trigger and trigger not in seen_triggers:
                seen_triggers.add(trigger)
                logger.info(f"WebSocket received new trigger: {trigger}", extra={"data_keys": list(data.keys())})
            
            if trigger in ["realtime_audio.mixed", "realtime_audio.user"]:
                # Inbound audio from candidate
                chunk_b64 = data.get("chunk")
                sample_rate = data.get("sample_rate", 24000)
                if chunk_b64 and session_id in active_sessions:
                    pcm_bytes = base64.b64decode(chunk_b64)
                    await orchestrator.stt_client.send_audio(pcm_bytes, sample_rate)
                    
    except WebSocketDisconnect:
        logger.info("Attendee WebSocket disconnected", extra={"session_id": session_id})
    finally:
        if session_id and session_id in active_sessions:
            orchestrator = active_sessions.pop(session_id)
            await orchestrator.cleanup()
