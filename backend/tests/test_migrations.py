from decimal import Decimal

from alembic import command
from sqlalchemy import Engine, create_engine, inspect, text

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


def test_price_range_migration_backfills_existing_bookings() -> None:
    """Rows created before the price-range migration get max == their old single price."""
    url = TEST_DATABASE_URL.set(database=f"{TEST_DATABASE_URL.database}_backfill")
    recreate_database(url)
    cfg = alembic_config(url)
    command.upgrade(cfg, "f3b7e2e5ff12")  # initial schema, before price ranges

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO customers (id, name, phone) VALUES (1, 'A', '+60123456789');"
                    "INSERT INTO services (id, name, description, pricing_unit, unit_price,"
                    " minimum_charge) VALUES (1, 'Karpet Biasa', '', 'per_sqft', 1.80, 0);"
                    "INSERT INTO bookings (id, customer_id, scheduled_start, scheduled_end,"
                    " estimated_price) VALUES (1, 1, now(), now() + interval '1 hour', 180);"
                    "INSERT INTO booking_items (booking_id, service_id, quantity, unit_price,"
                    " line_total) VALUES (1, 1, 100, 1.80, 180);"
                )
            )

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            booking_max = conn.scalar(text("SELECT estimated_price_max FROM bookings"))
            item = conn.execute(
                text("SELECT unit_price_max, line_total_max FROM booking_items")
            ).one()
            service_max = conn.scalar(text("SELECT unit_price_max FROM services"))
    finally:
        engine.dispose()

    assert booking_max == Decimal("180.00")
    assert tuple(item) == (Decimal("1.80"), Decimal("180.00"))
    assert service_max is None
