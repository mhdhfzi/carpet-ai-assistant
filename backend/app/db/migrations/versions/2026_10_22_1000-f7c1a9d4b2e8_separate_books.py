"""separate books: carpet orders and kerja luar orders, each numbered on its own

Revision ID: f7c1a9d4b2e8
Revises: e5b9c03d7a21
Create Date: 2026-10-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c1a9d4b2e8"
down_revision: str | Sequence[str] | None = "e5b9c03d7a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "orders",
        sa.Column(
            "kind",
            sa.Enum(
                "shop",
                "on_site",
                name="order_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="shop",
            nullable=False,
        ),
    )
    # An order of house jobs only moves to the kerja luar book. It keeps its number, so
    # receipts already sent stay right; new kerja luar orders continue after it.
    op.execute(
        "UPDATE orders o SET kind = 'on_site' "
        "WHERE EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.id) "
        "AND NOT EXISTS (SELECT 1 FROM order_items i JOIN services s ON s.id = i.service_id "
        "WHERE i.order_id = o.id AND NOT s.on_site)"
    )
    op.drop_constraint(op.f("uq_orders_number"), "orders", type_="unique")
    op.create_unique_constraint(op.f("uq_orders_kind_number"), "orders", ["kind", "number"])


def downgrade() -> None:
    """Downgrade schema."""
    # Two books may share a number; that can't be undone without renumbering, so refuse.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT number FROM orders GROUP BY number HAVING count(*) > 1) "
        "THEN RAISE EXCEPTION 'orders share numbers across books'; END IF; END $$"
    )
    op.drop_constraint(op.f("uq_orders_kind_number"), "orders", type_="unique")
    op.create_unique_constraint(op.f("uq_orders_number"), "orders", ["number"])
    op.drop_column("orders", "kind")
