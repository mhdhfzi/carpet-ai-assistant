import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app

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
def client(db: Session) -> Iterator[TestClient]:
    """An API client whose requests use the per-test session, so they're rolled back too."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
