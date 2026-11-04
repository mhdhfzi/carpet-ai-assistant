"""price caps: the most one carpet is charged (velvet RM50, premium velvet RM55), and a
price the owner agrees for one carpet

Revision ID: b173d5fc4e2a
Revises: f2b4d6e8a0c3
Create Date: 2026-11-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b173d5fc4e2a"
down_revision: str | Sequence[str] | None = "f2b4d6e8a0c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Money = sa.Numeric(10, 2)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("services", sa.Column("price_cap", Money, nullable=True))
    op.add_column("order_items", sa.Column("price_cap", Money, nullable=True))
    op.add_column("order_items", sa.Column("agreed_total", Money, nullable=True))
    # The caps the shop charges now; the seed sets the same. Old orders keep their prices:
    # only items recorded from now on take a cap.
    op.execute("UPDATE services SET price_cap = 50 WHERE name = 'Karpet Velvet'")
    op.execute("UPDATE services SET price_cap = 55 WHERE name = 'Karpet Premium Velvet'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("order_items", "agreed_total")
    op.drop_column("order_items", "price_cap")
    op.drop_column("services", "price_cap")
