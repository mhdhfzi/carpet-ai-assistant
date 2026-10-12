from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder, get_embedder
from app.ai.llm import ChatModel, get_chat_model
from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.services.whatsapp import (
    GraphWhatsAppClient,
    SessionFactory,
    WhatsAppClient,
    WhatsAppError,
)

DbSession = Annotated[Session, Depends(get_db)]


# Cached so every request reuses one HTTP client (connection pooling). A missing API key
# raises instead of returning, and lru_cache doesn't cache exceptions, so adding the key
# and restarting is enough. Tests replace these via app.dependency_overrides.
@lru_cache
def embedder_dependency() -> Embedder:
    return get_embedder()


@lru_cache
def chat_model_dependency() -> ChatModel:
    return get_chat_model()


EmbedderDep = Annotated[Embedder, Depends(embedder_dependency)]
ChatModelDep = Annotated[ChatModel, Depends(chat_model_dependency)]


# --- WhatsApp --------------------------------------------------------------------------------


@dataclass(frozen=True)
class WhatsAppConfig:
    verify_token: str | None
    app_secret: str | None


def whatsapp_config_dependency() -> WhatsAppConfig:
    settings = get_settings()
    return WhatsAppConfig(
        verify_token=_secret(settings.whatsapp_verify_token),
        app_secret=_secret(settings.whatsapp_app_secret),
    )


@lru_cache
def whatsapp_client_dependency() -> WhatsAppClient:
    settings = get_settings()
    if settings.whatsapp_access_token is None or settings.whatsapp_phone_number_id is None:
        raise WhatsAppError("WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID are not set")
    return GraphWhatsAppClient(
        settings.whatsapp_access_token.get_secret_value(),
        settings.whatsapp_phone_number_id,
        settings.whatsapp_api_version,
    )


def session_factory_dependency() -> SessionFactory:
    """Background tasks run after the request's session is closed, so they open their own."""
    return SessionLocal


WhatsAppConfigDep = Annotated[WhatsAppConfig, Depends(whatsapp_config_dependency)]
WhatsAppClientDep = Annotated[WhatsAppClient, Depends(whatsapp_client_dependency)]
SessionFactoryDep = Annotated[SessionFactory, Depends(session_factory_dependency)]


def _secret(value) -> str | None:
    return value.get_secret_value() if value is not None else None
