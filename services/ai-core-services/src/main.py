from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.v1 import parsing
from src.api.v1 import matching
from src.api.v1 import question_generation
from src.api.v1.meeting_bot import router as meeting_bot_router
from src.screening_pipeline.webhook_handler import router as webhook_router
from src.screening_pipeline.audio_websocket import router as websocket_router

import asyncio
from contextlib import asynccontextmanager
from src.screening_pipeline.pipecat_tts import KokoroSynthesizer, warm_shared_phrases
from src.screening_pipeline.recording_import import run_recording_import_poller
from src.screening_pipeline.tts_prewarm import known_bot_texts

def _warm_screening_imports() -> None:
    """Pay the screening pipeline's one-off import cost before any interview.

    The interview runtime is imported lazily (~7s) and Pipecat loads its
    deferred imports (~6s) while setting up the first pipeline, inside a 20s
    setup timeout. On the first interview after a (re)start, under CPU load
    (e.g. a TTS pre-warm), that timed out and the bot left the meeting.
    """
    import src.screening_pipeline.pipecat_runtime  # noqa: F401

    try:
        from pipecat.utils.prewarm import warm_deferred_imports
    except ImportError:
        return
    warm_deferred_imports()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(_warm_screening_imports)
    except Exception as e:
        print(f"Failed to warm screening pipeline imports: {e}")
    # Pre-download models on startup if they don't exist in the volume, then
    # synthesize the fixed bot lines (greeting, closing, fillers) once in the
    # background so every interview can speak its greeting the moment it joins.
    warm_task = None
    try:
        synthesizer = KokoroSynthesizer()
        await synthesizer.ensure_ready()
        warm_task = asyncio.create_task(
            warm_shared_phrases(synthesizer, known_bot_texts([]))
        )
    except Exception as e:
        print(f"Failed to pre-download Kokoro models: {e}")
    # Copies finished screenings' Attendee recordings into MinIO.
    recording_poller = asyncio.create_task(run_recording_import_poller())
    yield
    recording_poller.cancel()
    if warm_task is not None and not warm_task.done():
        warm_task.cancel()

app = FastAPI(
    title="EZScreen Service",
    description="Unified AI Microservice hosting Parsing, Matching, Screening, Attendee Bot, and Interview Analysis modules",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.service_name,
        "port": settings.port,
        "environment": settings.environment,
        "modules": ["parsing", "job_fit_analysis", "question_generation", "screening_pipeline", "meeting_bot", "interview_analysis"]    }


# Register API Routers
app.include_router(parsing.router, prefix="/internal/v1/parse")
app.include_router(matching.router, prefix="/internal/v1/match")
app.include_router(question_generation.router, prefix="/internal/v1/screening/questions")
app.include_router(meeting_bot_router)
app.include_router(webhook_router)
app.include_router(websocket_router)
