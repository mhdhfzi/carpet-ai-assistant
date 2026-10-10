"""add price ranges

Some services (e.g. handmade carpet) have a price range that the owner settles on inspection,
so services get an optional max price and bookings store a (min, max) estimate.

Revision ID: 799bd9977554
Revises: f3b7e2e5ff12
Create Date: 2026-10-10 21:04:39.073276

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "799bd9977554"
down_revision: str | Sequence[str] | None = "f3b7e2e5ff12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Money = sa.Numeric(precision=10, scale=2)

# (table, new max column, existing column it is backfilled from)
_RANGE_COLUMNS = [
    ("booking_items", "unit_price_max", "unit_price"),
    ("booking_items", "line_total_max", "line_total"),
    ("bookings", "estimated_price_max", "estimated_price"),
]

_CHECKS = [
    ("services", "unit_price_range", "unit_price_max IS NULL OR unit_price_max >= unit_price"),
    ("bookings", "estimated_price_range", "estimated_price_max >= estimated_price"),
    ("booking_items", "unit_price_range", "unit_price_max >= unit_price"),
    ("booking_items", "line_total_range", "line_total_max >= line_total"),
]


def upgrade() -> None:
    op.add_column("services", sa.Column("unit_price_max", Money, nullable=True))

    # Adding a NOT NULL column to a table with rows fails, so: add nullable, backfill
    # existing rows (their old single price is both min and max), then tighten.
    for table, column, source in _RANGE_COLUMNS:
        op.add_column(table, sa.Column(column, Money, nullable=True))
        op.execute(f"UPDATE {table} SET {column} = {source}")
        op.alter_column(table, column, nullable=False)

    for table, name, condition in _CHECKS:
        op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def downgrade() -> None:
    for table, name, _ in reversed(_CHECKS):
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")

    for table, column, _ in reversed(_RANGE_COLUMNS):
        op.drop_column(table, column)

    op.drop_column("services", "unit_price_max")
