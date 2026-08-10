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
