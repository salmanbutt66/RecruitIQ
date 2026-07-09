from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://recruitiq:recruitiq@localhost:5432/recruitiq"
    redis_url: str = "redis://localhost:6379"
    backend_base_url: str ="http://localhost:8000"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "recruitiq-resumes"
    minio_secure: bool = False

    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = "sk-recruitiq-local"
    groq_api_key: str = ""
    openai_api_key: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    resend_api_key: str = ""
    resend_from_email: str = "RecruitIQ <onboarding@resend.dev>"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_starter_price_id: str = ""
    stripe_professional_price_id: str = ""
    stripe_enterprise_price_id: str = ""

    logfire_token: str = ""
    logfire_project: str = "recruitiq"

    frontend_url: str = "http://localhost:3000"
    admin_url: str = "http://localhost:3001"
    api_url: str = "http://localhost:8000"

    borderline_score_min: int = 35
    borderline_score_max: int = 40
    screening_concurrency: int = 5
    max_upload_size_mb: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
