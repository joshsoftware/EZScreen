from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-screening")

app = FastAPI(
    title="EZScreen AI Screening Service",
    description="Microservice for handling live screening calls, WebSockets, STT-LLM-TTS pipelines, and Attendee bot synchronization",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ai-screening",
        "websockets": "active"
    }

@app.websocket("/attendee-websocket")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Attendee bot connected to WebSocket")
    try:
        while True:
            # Receive text or binary frame
            data = await websocket.receive_text()
            payload = json.loads(data)
            trigger = payload.get("trigger")
            
            if trigger == "realtime_audio.mixed":
                chunk = payload.get("data", {}).get("chunk")
                sample_rate = payload.get("data", {}).get("sample_rate", 24000)
                
                # In a real pipeline, we would stream this base64 PCM chunk to STT.
                # For the skeleton, we just log that we received it.
                logger.info(f"Received mixed audio chunk of length {len(chunk)} at {sample_rate}Hz")
                
                # Placeholder response: send silent frames or echo back if needed.
                # In real code: we would run LLM chain -> TTS -> synthesize audio -> send bot_output chunk.
                response_payload = {
                    "trigger": "realtime_audio.bot_output",
                    "data": {
                        "chunk": base64.b64encode(b"\x00" * 480).decode("utf-8"),  # silent frame
                        "sample_rate": sample_rate
                    }
                }
                await websocket.send_text(json.dumps(response_payload))
            else:
                logger.warning(f"Received unknown WebSocket payload trigger: {trigger}")
    except WebSocketDisconnect:
        logger.info("Attendee bot disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
