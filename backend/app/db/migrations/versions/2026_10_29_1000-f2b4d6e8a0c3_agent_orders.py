"""agent orders: a customer who is an agent (ejen) and the orders taken at agent prices

Revision ID: f2b4d6e8a0c3
Revises: e1a3c5d7f9b2
Create Date: 2026-10-29 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b4d6e8a0c3"
down_revision: str | Sequence[str] | None = "e1a3c5d7f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "customers",
        sa.Column("is_agent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "orders", sa.Column("agent", sa.Boolean(), server_default="false", nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("orders", "agent")
    op.drop_column("customers", "is_agent")
