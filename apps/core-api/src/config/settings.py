from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Secrets must come from environment / .env — never commit them."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required. Set in apps/core-api/.env (not committed).
    database_url: str
    jwt_secret: str
    internal_service_token: str | None = None

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "ezscreen_refresh"
    refresh_cookie_path: str = "/api/v1/auth"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # MinIO / S3 (local dev defaults match docker-compose)
    minio_endpoint: str = "host.docker.internal:9000"
    # Server-side boto3 (get_object). In Docker use minio:9000; presigned URLs use minio_endpoint.
    minio_internal_endpoint: str | None = None
    minio_access_key: str = "minio_admin"
    minio_secret_key: str = "minio_password"
    minio_secure: bool = False
    minio_bucket_resumes: str = "resumes"
    s3_presign_expires_seconds: int = 900

    # AI core host. Change this once; URL is derived unless PARSING_SERVICE_URL is set.
    ai_services_host: str = "127.0.0.1"
    ai_services_port: int = 8002
    ai_services_scheme: str = "http"
    parsing_service_url: str | None = None

    @field_validator("parsing_service_url", mode="before")
    @classmethod
    def _optional_parsing_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.split(",")[0].strip()
        return cleaned or None

    # Password reset (org admin / HR). Email delivery not wired yet —
    # when expose_link is true, API returns reset_url for local/dev use.
    frontend_base_url: str = "http://localhost:5173"
    password_reset_expire_minutes: int = 60
    password_reset_expose_link: bool = True

    # Outbound email. console = log invite body (local/dev). smtp reserved for later.
    email_mode: str = "console"
    email_from: str = "noreply@ezscreen.io"

    # Google Calendar + Meet for screening interviews.
    # mock = placeholder meet.google.com URL (local/dev default)
    # live = Calendar event with Meet link + Google attendee invites
    google_meet_mode: str = "mock"
    google_calendar_id: str = "primary"
    google_calendar_send_updates: str = "all"
    google_service_account_file: str | None = None
    google_meet_delegated_user: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_refresh_token: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def s3_endpoint_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        return f"{scheme}://{self.minio_endpoint}"

    @property
    def s3_internal_endpoint_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        host = (self.minio_internal_endpoint or self.minio_endpoint).strip()
        return f"{scheme}://{host}"

    @property
    def ai_services_base_url(self) -> str:
        if self.parsing_service_url:
            base = self.parsing_service_url.rstrip("/")
            if base.endswith("/internal/v1"):
                return base[: -len("/internal/v1")]
            return base
        host = self.ai_services_host.strip()
        return f"{self.ai_services_scheme}://{host}:{self.ai_services_port}"

    @property
    def parsing_service_base_url(self) -> str:
        if self.parsing_service_url:
            return self.parsing_service_url.rstrip("/")
        return f"{self.ai_services_base_url}/internal/v1"


settings = Settings()
