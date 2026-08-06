from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        "service": "ai-service",
        "port": 8002,
        "modules": ["parsing", "matching-result", "question-generation", "screening-pipeline", "meeting-bot", "interview-analysis"]
    }
