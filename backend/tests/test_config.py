"""Tests for application settings / config loading."""

from app.config import Settings, get_settings


def test_settings_defaults(monkeypatch):
    # Clear env vars that Docker Compose sets so we test true defaults
    for key in ("DATABASE_URL", "REDIS_URL", "GROQ_API_KEY", "GROQ_MODEL"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.app_name == "AeroTwin"
    assert settings.app_env == "development"
    assert settings.database_url.startswith("postgresql+asyncpg")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 60
    assert settings.simulator_interval_ms == 1000
    assert settings.simulator_enabled is True


def test_settings_loads_groq_key_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123456789")
    # get_settings is lru_cached; create a fresh Settings directly
    settings = Settings()
    assert settings.groq_api_key == "gsk_test123456789"


def test_get_settings_returns_settings_instance():
    s = get_settings()
    assert isinstance(s, Settings)


def test_groq_model_default_and_env_override(monkeypatch):
    assert Settings(_env_file=None).groq_model == "openai/gpt-oss-120b"
    monkeypatch.setenv("GROQ_MODEL", "qwen/qwen3.6-27b")
    assert Settings(_env_file=None).groq_model == "qwen/qwen3.6-27b"


def test_settings_parse_types_from_env(monkeypatch):
    monkeypatch.setenv("SIMULATOR_INTERVAL_MS", "250")
    monkeypatch.setenv("SIMULATOR_ENABLED", "false")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "5")
    s = Settings(_env_file=None)
    assert (s.simulator_interval_ms, s.simulator_enabled, s.access_token_expire_minutes) == (250, False, 5)


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
