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
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://carpet:carpet@127.0.0.1:5432/carpet"
    # Websites allowed to call the API from a browser (the chat widget), comma-separated,
    # e.g. "https://demo.example.com,https://www.example.com". Empty = none.
    cors_origins: str = ""
    # Built frontend (demo page, dashboard, widget.js) to serve from the same origin as the
    # API. Set in the Docker image; unset in development, where Vite serves the frontend.
    static_dir: str | None = None

    # Owner login. Tokens are signed with this secret: long, random, never committed.
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = 8 * 60

    # Embeddings for RAG. SecretStr keeps the key out of logs and error messages.
    voyage_api_key: SecretStr | None = None
    embedding_model: str = "voyage-3.5"

    # Chat model (Claude). Swap to a cheaper model here if cost matters more than quality.
    anthropic_api_key: SecretStr | None = None
    chat_model: str = "claude-opus-5-5"
    # Most AI replies per day (Malaysia time) across all customers: a cost guard for the
    # public demo. Beyond it customers get a polite fixed reply. 0 = no limit.
    ai_daily_reply_limit: int = 300

    # WhatsApp Business Cloud API. All optional: without the app secret the webhook refuses
    # every request, so unsigned (forged) messages are never processed.
    whatsapp_verify_token: SecretStr | None = None  # chosen by us, entered in Meta's dashboard
    whatsapp_app_secret: SecretStr | None = None  # signs every webhook request
    whatsapp_access_token: SecretStr | None = None  # for sending replies
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str = "v23.0"

    @field_validator(
        "jwt_secret",
        "voyage_api_key",
        "anthropic_api_key",
        "whatsapp_verify_token",
        "whatsapp_app_secret",
        "whatsapp_access_token",
        "whatsapp_phone_number_id",
        mode="before",
    )
    @classmethod
    def _blank_key_means_unset(cls, value: object) -> object:
        # .env.example ships `KEY=` lines; an empty value must count as missing,
        # not as a key made of an empty string.
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def json_logs(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so env parsing happens once per process."""
    return Settings()
