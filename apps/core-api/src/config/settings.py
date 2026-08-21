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

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "ezscreen_refresh"
    refresh_cookie_path: str = "/api/v1/auth"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # MinIO / S3 (local dev defaults match docker-compose)
    minio_endpoint: str = "172.60.1.147:9000"
    minio_access_key: str = "minio_admin"
    minio_secret_key: str = "minio_password"
    minio_secure: bool = False
    minio_bucket_resumes: str = "resumes"
    s3_presign_expires_seconds: int = 900

    # Internal parsing service (resume extraction)
    parsing_service_url: str = "http://127.0.0.1:8002/internal/v1"

    # Password reset (org admin / HR). Email delivery not wired yet —
    # when expose_link is true, API returns reset_url for local/dev use.
    frontend_base_url: str = "http://localhost:5173"
    password_reset_expire_minutes: int = 60
    password_reset_expose_link: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def s3_endpoint_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        return f"{scheme}://{self.minio_endpoint}"


settings = Settings()
