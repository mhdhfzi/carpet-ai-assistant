"""order charges: extra charges on an order, each with its reason (a pickup over 15km, a
special chemical)

Revision ID: c4e6a8b0d2f1
Revises: b173d5fc4e2a
Create Date: 2026-11-11 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e6a8b0d2f1"
down_revision: str | Sequence[str] | None = "b173d5fc4e2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Money = sa.Numeric(10, 2)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "order_charges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("amount", Money, nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.CheckConstraint("amount > 0", name=op.f("ck_order_charges_amount_positive")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_charges_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_charges")),
    )
    op.create_index(op.f("ix_order_charges_order_id"), "order_charges", ["order_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_order_charges_order_id"), table_name="order_charges")
    op.drop_table("order_charges")
