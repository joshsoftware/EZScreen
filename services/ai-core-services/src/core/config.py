import os

class Settings:
    SERVICE_NAME: str = "ai-service"
    PORT: int = 8002
    
    # LLM Settings
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemma4:31b")
    
    # Attendee.dev Bot Credentials
    ATTENDEE_API_KEY: str = os.getenv("ATTENDEE_API_KEY", "")
    ATTENDEE_API_URL: str = os.getenv("ATTENDEE_API_URL", "https://api.attendee.dev/v1")

settings = Settings()
