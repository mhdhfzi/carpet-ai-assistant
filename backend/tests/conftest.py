import os
from collections.abc import Iterator
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.api.deps import (
    WhatsAppConfig,
    chat_model_dependency,
    embedder_dependency,
    session_factory_dependency,
    whatsapp_client_dependency,
    whatsapp_config_dependency,
)
from app.core import clock
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.models import Owner
from app.db.session import get_db
from app.main import create_app
from tests.fakes import FakeChatModel, FakeEmbedder, FakeWhatsAppClient

WHATSAPP_TEST_CONFIG = WhatsAppConfig(
    verify_token="test-verify-token", app_secret="test-app-secret"
)

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_DATABASE_URL = make_url(
    os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://carpet:carpet@127.0.0.1:5432/carpet_test")
)


def recreate_database(url: URL) -> None:
    """Drop and create an empty database, connecting via the default `postgres` database."""
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


def alembic_config(url: URL) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    # ConfigParser treats % as interpolation, so escape it (e.g. in URL-encoded passwords).
    cfg.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    return cfg


# Saturday 10 Oct 2026, 10:00 in Malaysia. With 2 days' notice, Monday 12 Oct is the earliest
# bookable day. Freezing time keeps date-based tests from breaking as the calendar moves on.
FROZEN_NOW = datetime(2026, 10, 10, 10, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> datetime:
    monkeypatch.setattr(clock, "now", lambda: FROZEN_NOW)
    return FROZEN_NOW


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A fresh test database, migrated to head once per test session."""
    recreate_database(TEST_DATABASE_URL)
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose changes are rolled back after each test, keeping tests isolated.

    `create_savepoint` lets code under test call commit()/rollback() freely: those act on a
    SAVEPOINT, while the outer transaction is always rolled back at the end.
    """
    with engine.connect() as conn:
        outer = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_llm() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def fake_whatsapp() -> FakeWhatsAppClient:
    return FakeWhatsAppClient()


# --- Owner authentication ------------------------------------------------------------------

TEST_JWT_SECRET = "test-jwt-secret-that-is-long-enough-for-hs256"
OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "correct horse battery staple"
# Hashed once per run: Argon2 is deliberately slow, and most tests just need an owner.
_OWNER_PASSWORD_HASH = hash_password(OWNER_PASSWORD)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield TEST_JWT_SECRET
    get_settings.cache_clear()


@pytest.fixture
def owner(db: Session) -> Owner:
    owner = Owner(email=OWNER_EMAIL, name="Test Owner", password_hash=_OWNER_PASSWORD_HASH)
    db.add(owner)
    db.flush()
    return owner


@pytest.fixture
def owner_token(owner: Owner) -> str:
    return create_access_token(owner.id)[0]


# --- API clients ----------------------------------------------------------------------------


def _test_app(db: Session, embedder, llm, whatsapp) -> FastAPI:
    """The app wired to the per-test session, so API changes are rolled back too.

    AI providers and WhatsApp are always replaced with fakes, so no test can call a paid or
    external API.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[embedder_dependency] = lambda: embedder
    app.dependency_overrides[chat_model_dependency] = lambda: llm
    app.dependency_overrides[whatsapp_client_dependency] = lambda: whatsapp
    app.dependency_overrides[whatsapp_config_dependency] = lambda: WHATSAPP_TEST_CONFIG
    # Background tasks reuse the test's session (wrapped so they can't close it).
    app.dependency_overrides[session_factory_dependency] = lambda: lambda: nullcontext(db)
    return app


@pytest.fixture
def client(
    db: Session,
    fake_embedder: FakeEmbedder,
    fake_llm: FakeChatModel,
    fake_whatsapp: FakeWhatsAppClient,
    owner_token: str,
) -> Iterator[TestClient]:
    """API client logged in as the owner (customer endpoints simply ignore the token)."""
    app = _test_app(db, fake_embedder, fake_llm, fake_whatsapp)
    with TestClient(app, headers={"Authorization": f"Bearer {owner_token}"}) as client:
        yield client


@pytest.fixture
def anon_client(
    db: Session,
    fake_embedder: FakeEmbedder,
    fake_llm: FakeChatModel,
    fake_whatsapp: FakeWhatsAppClient,
) -> Iterator[TestClient]:
    """API client with no login, like a customer or an attacker."""
    with TestClient(_test_app(db, fake_embedder, fake_llm, fake_whatsapp)) as client:
        yield client
