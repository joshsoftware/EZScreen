from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    SERVICE_NAME: str = "ai-core-services"
    PORT: int = 8002
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Ollama Cloud Credentials & Configuration
    OLLAMA_URL: str = "https://api.ollama.com"
    OLLAMA_MODEL: str = "gemma4:31b"
    OLLAMA_API_KEY: str = ""

    # Attendee.dev Meeting Bot Credentials
    ATTENDEE_API_KEY: str = ""
    ATTENDEE_API_URL: str = "https://api.attendee.dev/v1"

    # Database Connection
    DATABASE_URL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR.parent.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
