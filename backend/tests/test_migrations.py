from alembic import command
from sqlalchemy import Engine, create_engine, inspect

from tests.conftest import TEST_DATABASE_URL, alembic_config, recreate_database


def test_models_match_migrations(engine: Engine) -> None:
    """Fails if someone changes a model without generating a migration for it."""
    command.check(alembic_config(TEST_DATABASE_URL))


def test_upgrade_downgrade_roundtrip() -> None:
    """Every migration can be applied, fully reverted, and applied again."""
    url = TEST_DATABASE_URL.set(database=f"{TEST_DATABASE_URL.database}_migrations")
    recreate_database(url)
    cfg = alembic_config(url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert {"services", "customers", "bookings", "booking_items", "conversations", "messages"} <= (
        tables
    )
