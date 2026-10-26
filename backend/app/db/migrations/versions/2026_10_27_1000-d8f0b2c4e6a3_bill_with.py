"""bill with: a carpet order and a kerja luar order of the same customer share one bill

Revision ID: d8f0b2c4e6a3
Revises: c7e9a1b3d5f2
Create Date: 2026-10-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8f0b2c4e6a3"
down_revision: str | Sequence[str] | None = "c7e9a1b3d5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("orders", sa.Column("bill_with_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_bill_with_id_orders"),
        "orders",
        "orders",
        ["bill_with_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_orders_bill_with_id_orders"), "orders", type_="foreignkey")
    op.drop_column("orders", "bill_with_id")
