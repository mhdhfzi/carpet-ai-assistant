import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.ai.llm import LLMAnswer
from app.api.deps import chat_model_dependency, embedder_dependency
from app.core import clock
from app.db.session import get_db
from app.main import create_app
from tests.fakes import FakeChatModel, FakeEmbedder

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
    return FakeChatModel(LLMAnswer("Hello from the fake model."))


@pytest.fixture
def client(
    db: Session, fake_embedder: FakeEmbedder, fake_llm: FakeChatModel
) -> Iterator[TestClient]:
    """An API client whose requests use the per-test session, so they're rolled back too.

    AI providers are always replaced with fakes, so no test can call a paid API.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[embedder_dependency] = lambda: fake_embedder
    app.dependency_overrides[chat_model_dependency] = lambda: fake_llm
    with TestClient(app) as client:
        yield client
