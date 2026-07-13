from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (see /.env.example)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "vaultly-api"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"

    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Auth. secret_key MUST be overridden outside local/test (validated at startup).
    secret_key: str = "dev-only-secret-change-me"  # noqa: S105 — dev default, blocked in prod
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False  # true behind TLS in staging/production

    database_url: str = "postgresql+asyncpg://vaultly:vaultly@localhost:5432/vaultly"
    redis_url: str = "redis://localhost:6379/0"

    # Object storage (MinIO locally, S3 in production)
    s3_endpoint_url: str = "http://localhost:9000"
    # What the *browser* can reach for presigned URLs (differs from s3_endpoint_url in Docker)
    s3_public_endpoint_url_override: str | None = None
    s3_bucket: str = "vaultly-documents"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    @property
    def s3_public_endpoint_url(self) -> str:
        return self.s3_public_endpoint_url_override or self.s3_endpoint_url

    # Email (Mailpit locally, SES/Resend in production)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "reminders@vaultly.local"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
