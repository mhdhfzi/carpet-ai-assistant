"""cancel one item of an order: kept on the order, crossed out, so the other tags keep
their numbers

Revision ID: a3c5e7f9b1d2
Revises: f7c1a9d4b2e8
Create Date: 2026-10-23 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c5e7f9b1d2"
down_revision: str | Sequence[str] | None = "f7c1a9d4b2e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("order_items", sa.Column("cancelled_on", sa.Date(), nullable=True))
    op.add_column("order_items", sa.Column("cancelled_by_id", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_order_items_cancelled_by_id_owners"),
        "order_items",
        "owners",
        ["cancelled_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_order_items_cancelled_by_id_owners"), "order_items", type_="foreignkey"
    )
    op.drop_column("order_items", "cancel_reason")
    op.drop_column("order_items", "cancelled_by_id")
    op.drop_column("order_items", "cancelled_on")
