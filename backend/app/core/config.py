"""Application settings, loaded from environment variables (and a local .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so env parsing happens once per process."""
    return Settings()
