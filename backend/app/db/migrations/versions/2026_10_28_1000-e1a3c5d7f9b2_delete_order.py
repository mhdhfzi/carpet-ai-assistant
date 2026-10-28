"""delete an order made by mistake: hidden everywhere, kept for the owner to restore; a
deleted order's number can be used again

Revision ID: e1a3c5d7f9b2
Revises: d8f0b2c4e6a3
Create Date: 2026-10-28 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a3c5d7f9b2"
down_revision: str | Sequence[str] | None = "d8f0b2c4e6a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("orders", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("delete_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_deleted_by_id_owners"),
        "orders",
        "owners",
        ["deleted_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Numbers are unique among the orders that aren't deleted, so a deleted duplicate's
    # number can go to the next order.
    op.drop_constraint(op.f("uq_orders_kind_number"), "orders", type_="unique")
    op.create_index(
        op.f("uq_orders_kind_number"),
        "orders",
        ["kind", "number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Deleted orders may share a number with a live one: they go for good on the way down.
    op.execute("DELETE FROM orders WHERE deleted_at IS NOT NULL")
    op.drop_index(op.f("uq_orders_kind_number"), table_name="orders")
    op.create_unique_constraint(op.f("uq_orders_kind_number"), "orders", ["kind", "number"])
    op.drop_constraint(op.f("fk_orders_deleted_by_id_owners"), "orders", type_="foreignkey")
    op.drop_column("orders", "delete_reason")
    op.drop_column("orders", "deleted_by_id")
    op.drop_column("orders", "deleted_at")
