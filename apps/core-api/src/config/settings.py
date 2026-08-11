from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg2://ezscreen_user:EZScreen123!@127.0.0.1:5432/ezscreen_db"
    )

settings = Settings()