"""AeroTwin Backend Configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "AeroTwin"
    app_env: str = "development"
    log_level: str = "INFO"

    # Groq LLM
    groq_api_key: str = ""
    # Groq retires models regularly (llama-3.1-70b-versatile and llama-3.3-70b-versatile are gone),
    # so the model id is configurable via GROQ_MODEL.
    groq_model: str = "openai/gpt-oss-120b"

    # Database
    database_url: str = "postgresql+asyncpg://aerotwin:aerotwin_secret_2026@localhost:5432/aerotwin"
    postgres_user: str = "aerotwin"
    postgres_password: str = "aerotwin_secret_2026"
    postgres_db: str = "aerotwin"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT Auth
    jwt_secret_key: str = "aerotwin-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Simulator
    simulator_interval_ms: int = 1000
    simulator_enabled: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

