"""size later: a carpet's size can be measured when it is washed

Revision ID: d2a8f61c3e57
Revises: c41d7e9a2b10
Create Date: 2026-10-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2a8f61c3e57"
down_revision: str | Sequence[str] | None = "c41d7e9a2b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # NULL: a carpet not measured yet (its price is then pending).
    op.alter_column(
        "order_items", "quantity", existing_type=sa.Numeric(precision=10, scale=2), nullable=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM order_items WHERE quantity IS NULL")
    op.alter_column(
        "order_items", "quantity", existing_type=sa.Numeric(precision=10, scale=2), nullable=False
    )
