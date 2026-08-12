from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings

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
        "modules": ["parsing", "job_fit_analysis", "question_generation", "screening_pipeline", "meeting_bot", "interview_analysis"]
    }



