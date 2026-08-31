from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.v1 import parsing
from src.api.v1 import matching
from src.api.v1 import question_generation
from src.api.v1.meeting_bot import router as meeting_bot_router
from src.screening_pipeline.webhook_handler import router as webhook_router

app = FastAPI(
    title="EZScreen Service",
    description="Unified AI Microservice hosting Parsing, Matching, Screening, Attendee Bot, and Interview Analysis modules",
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
