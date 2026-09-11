from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from the environment or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Defaulting to SQLite keeps `git clone && uvicorn` working with no setup.
    # Production overrides this with a Neon Postgres URL; nothing else changes.
    database_url: str = "sqlite:///./patients.db"

    vapi_shared_secret: str = "change-me"

    llm_provider: str = "vapi"
    gemini_api_key: str | None = None
    groq_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
