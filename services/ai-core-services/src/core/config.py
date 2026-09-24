import sys
from pathlib import Path
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    service_name: str 
    port: int
    environment: str 
    log_level: str

    # Ollama Cloud Credentials & Configuration
    ollama_url: str 
    ollama_model: str 
    ollama_api_key: str 

    # Attendee.dev Meeting Bot Credentials
    attendee_api_key: str
    attendee_api_url: str

    # Database & Storage Connection Credentials
    database_url: str

    # Object Storage (MinIO)
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False
    minio_bucket_name: str

    # Real-time WebSocket Audio Stream Endpoint
    websocket_url: str
    
    # Webhook callback URL for Attendee to post lifecycle events to
    webhook_url: str
    
    # Internal URL for Core API (to update DB state)
    core_api_url: str
    
    # Whisper STT (Cloud API)
    whisper_api_url: str | None = None
    whisper_api_key: str | None = None
    
    # Kokoro TTS (Cloud API)
    kokoro_api_url: str | None = None
    kokoro_api_key: str | None = None
    ai_models_host_dir: str | None = None
    kokoro_model_path: str | None = None
    kokoro_voices_path: str | None = None
    kokoro_allow_download: bool = False

    # Docling
    docling_do_ocr: bool = True

    # RapidOCR settings for PDF page rendering
    ocr_scale: float = 3.0
    ocr_max_pages: int = 20

    # core-api (screening persistence callbacks)
    core_api_base_url: str = "http://127.0.0.1:8000"
    internal_service_token: str | None = None

    # Screening turn-latency tuning (docs/architecture/SCREENING_BOT_LATENCY_OPTIMIZATION.md Phase 2).
    # Time Pipecat's VAD waits after the candidate stops talking before finalizing
    # the STT segment. Hard floor is 1.0s — do not go lower without UX sign-off.
    screening_turn_end_silence_seconds: float = 1.5
    # Time the policy holds a finalized STT segment before evaluating it, so a
    # brief pause mid-answer is merged into one answer instead of two. Hard
    # floor is 1.5s — do not go lower without UX sign-off.
    screening_answer_settle_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR.parent.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


try:
    settings = Settings()
except ValidationError as err:
    sys.stderr.write(f"[FATAL] Configuration validation error loading settings from .env:\n{err}\n")
    sys.exit(1)
