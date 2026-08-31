import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
from src.core.logger import logger

router = APIRouter(tags=["Attendee WebSocket"])

# We will manage active sessions here
active_sessions: Dict[str, Any] = {}

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

@router.websocket("/attendee-websocket")
async def attendee_audio_ws(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional audio streaming.
    Attendee will connect to this URL.
    """
    await websocket.accept()
    logger.info("Attendee connected to WebSocket")
    
    bot_id = None
    
    try:
        while True:
            message = await websocket.receive_json()
            trigger = message.get("trigger")
            data = message.get("data", {})
            
            if trigger == "realtime_audio.mixed":
                # Inbound audio from candidate
                chunk_b64 = data.get("chunk")
                if chunk_b64 and bot_id and bot_id in active_sessions:
                    pcm_bytes = base64.b64decode(chunk_b64)
                    orchestrator = active_sessions[bot_id]
                    await orchestrator.stt_client.send_audio(pcm_bytes)
                    
            elif trigger == "bot.joined":
                # Initial payload sent upon connection
                bot_id = data.get("bot_id")
                
                from src.screening_pipeline.orchestrator import InterviewOrchestrator
                orchestrator = InterviewOrchestrator(bot_id=bot_id, websocket=websocket)
                active_sessions[bot_id] = orchestrator
                
                logger.info("Bot audio stream initialized", extra={"bot_id": bot_id})
                
                # Start the orchestrator logic
                import asyncio
                asyncio.create_task(orchestrator.start())
                
    except WebSocketDisconnect:
        logger.info("Attendee WebSocket disconnected", extra={"bot_id": bot_id})
    finally:
        if bot_id and bot_id in active_sessions:
            orchestrator = active_sessions.pop(bot_id)
            await orchestrator.cleanup()
