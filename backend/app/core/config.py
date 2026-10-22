"""Application settings, loaded from environment variables (and a local .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.duitnow import is_valid_qr


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
    # The owner's on/off switch for the chat. Off: the widget hides its button.
    chat_enabled: bool = True
    # The back office (orders, customers) in the dashboard: for a real business.
    orders_enabled: bool = False
    # Printed on receipts. All optional; blank lines are left out.
    receipt_name: str = ""  # the name on the receipt, if not the business name
    receipt_logo: str = ""  # the short mark in the round badge, e.g. "RGL"; blank = initials
    # A logo picture for the badge instead of letters, e.g. "/brand/rgl-mark.png" (a file the
    # dashboard serves). Blank = the letters above.
    receipt_logo_image: str = ""
    business_reg_no: str = ""  # e.g. the SSM registration number
    business_address: str = ""
    business_email: str = ""
    business_facebook: str = ""  # the Facebook page's name
    business_phones: str = ""  # e.g. "019-276 2890 / 013-397 9447"; blank = contact_whatsapp
    # How to pay, one item per line (new lines or "|"), e.g. "Name|Bank Islam|0506...".
    payment_details: str = ""
    receipt_terms: str = ""  # small print, e.g. how long unclaimed items are kept
    # The shop's DuitNow QR (the text inside it, read from the bank's QR): the dashboard draws
    # it so a customer can scan and pay. Blank = no QR button.
    duitnow_qr: str = ""

    # The business this deployment serves. The defaults are the public portfolio demo; a
    # deployment for a real business overrides them (one codebase, several deployments).
    business_name: str = "Kilau Carpet Care"
    business_location: str = "Seremban, serving all of Negeri Sembilan, Malaysia"
    # True: the assistant tells customers the business is fictional and bookings aren't real.
    demo_business: bool = True
    # Folder of knowledge documents to ingest; unset = backend/knowledge (the demo's).
    knowledge_dir: str | None = None
    # False: the assistant answers questions and gives estimates only, and sends customers
    # to WhatsApp to book. The booking tools are then not offered to the model at all.
    bookings_enabled: bool = True
    # The WhatsApp number customers are sent to when they need a person, as written for
    # customers (e.g. "012-345 6789"). Required when bookings are disabled.
    contact_whatsapp: str | None = None

    # WhatsApp Business Cloud API. All optional: without the app secret the webhook refuses
    # every request, so unsigned (forged) messages are never processed.
    whatsapp_verify_token: SecretStr | None = None  # chosen by us, entered in Meta's dashboard
    whatsapp_app_secret: SecretStr | None = None  # signs every webhook request
    whatsapp_access_token: SecretStr | None = None  # for sending replies
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str = "v23.0"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Hosted Postgres providers (e.g. Neon) hand out postgresql:// or postgres:// URLs;
        # SQLAlchemy needs the driver named, so accept those as-is and add it.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

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

    @field_validator("duitnow_qr")
    @classmethod
    def _qr_must_be_whole(cls, value: str) -> str:
        # Fail at startup rather than show customers a QR their bank app rejects.
        value = value.strip()
        if value and not is_valid_qr(value):
            raise ValueError("DUITNOW_QR is not a complete DuitNow QR code (checksum mismatch)")
        return value

    @model_validator(mode="after")
    def _answers_only_needs_a_contact(self) -> "Settings":
        # Fail at startup, not mid-conversation: without bookings the assistant's only way
        # to help with a booking is to give this number.
        if not self.bookings_enabled and not (self.contact_whatsapp or "").strip():
            raise ValueError("CONTACT_WHATSAPP is required when BOOKINGS_ENABLED is false")
        return self

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
