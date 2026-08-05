from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="EZScreen Core API",
    description="Backend Platform API for EZScreen candidate screening and ATS management",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adapt this to specific hosts in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to EZScreen Core API"}

@app.get("/api/v1/system/health")
def health_check():
    # Basic health metadata
    return {
        "status": "healthy",
        "service": "core-api",
        "database_url_configured": bool(os.getenv("DATABASE_URL")),
        "minio_endpoint_configured": bool(os.getenv("MINIO_ENDPOINT"))
    }
