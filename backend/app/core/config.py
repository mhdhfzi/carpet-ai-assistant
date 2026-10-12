"""Application settings, loaded from environment variables (and a local .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Carpet AI Assistant"
    environment: Literal["local", "test", "production"] = "local"
    debug: bool = False
    database_url: str = "postgresql+psycopg://carpet:carpet@127.0.0.1:5432/carpet"

    # Embeddings for RAG. SecretStr keeps the key out of logs and error messages.
    voyage_api_key: SecretStr | None = None
    embedding_model: str = "voyage-3.5"

    # Chat model (Claude). Swap to a cheaper model here if cost matters more than quality.
    anthropic_api_key: SecretStr | None = None
    chat_model: str = "claude-opus-5-5"

    @field_validator("voyage_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def _blank_key_means_unset(cls, value: object) -> object:
        # .env.example ships `KEY=` lines; an empty value must count as missing,
        # not as a key made of an empty string.
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so env parsing happens once per process."""
    return Settings()
