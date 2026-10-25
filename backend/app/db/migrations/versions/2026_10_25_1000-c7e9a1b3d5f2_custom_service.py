"""custom service ("Lain-lain"): a job off the price list, described and priced when the
order is taken

Revision ID: c7e9a1b3d5f2
Revises: b6d8f0a2c4e1
Create Date: 2026-10-25 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e9a1b3d5f2"
down_revision: str | Sequence[str] | None = "b6d8f0a2c4e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "services",
        sa.Column("custom", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("services", "custom")
