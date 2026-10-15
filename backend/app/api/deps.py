from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder, get_embedder
from app.ai.llm import ChatModel, get_chat_model
from app.core.config import get_settings
from app.core.security import AuthError, ForbiddenError, ReadOnlyAccountError, decode_access_token
from app.db.models import Owner, OwnerRole
from app.db.session import SessionLocal, get_db
from app.services.errors import NotFoundError
from app.services.whatsapp import (
    GraphWhatsAppClient,
    SessionFactory,
    WhatsAppClient,
    WhatsAppError,
)

DbSession = Annotated[Session, Depends(get_db)]


# --- Owner authentication ----------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)

# Methods that only read. Anything else changes data.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def current_owner(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Owner:
    """The logged-in owner, from the Authorization: Bearer token.

    The owner is reloaded on every request, so a deleted account's token stops working
    immediately instead of when it expires.

    The demo account is read-only, checked here by HTTP method rather than per route: deny
    by default, so a write endpoint added later is protected without anyone remembering to.
    """
    if credentials is None:
        raise AuthError("Not logged in")
    owner = db.get(Owner, decode_access_token(credentials.credentials))
    if owner is None:
        raise AuthError("This account no longer exists")
    if owner.role is OwnerRole.DEMO and request.method not in SAFE_METHODS:
        raise ReadOnlyAccountError("The demo account is read-only")
    if owner.role is OwnerRole.STAFF and not _staff_may(request):
        raise ForbiddenError("Staff accounts can't do this")
    return owner


# Staff (workers) record orders and look up customers and prices; everything else (chats,
# analytics, bookings, settings) is the owner's. Allow-listed, so anything new is denied.
STAFF_PATHS = ("/api/orders", "/api/customers")
STAFF_READ_PATHS = ("/api/services", "/api/auth/me")


def _staff_may(request: Request) -> bool:
    path = request.url.path
    if _under(path, STAFF_PATHS):
        return True
    return request.method in SAFE_METHODS and _under(path, STAFF_READ_PATHS)


def _under(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def orders_enabled() -> None:
    """Router dependency: the back office exists only where ORDERS_ENABLED is on."""
    if not get_settings().orders_enabled:
        raise NotFoundError("Not found")


RequireOrdersEnabled = Depends(orders_enabled)


CurrentOwner = Annotated[Owner, Depends(current_owner)]
# For whole routers or single routes: dependencies=[RequireOwner]
RequireOwner = Depends(current_owner)


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
