"""handmade / premium: "Karpet Handmade" is renamed "Karpet Handmade / Premium"

Renamed in place, so it keeps its id: old orders' handmade carpets show the new name, and
the seed (which matches services by name) updates it instead of adding a second one.

Revision ID: d5f7b9c1e3a4
Revises: c4e6a8b0d2f1
Create Date: 2026-11-25 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f7b9c1e3a4"
down_revision: str | Sequence[str] | None = "c4e6a8b0d2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE services SET name = 'Karpet Handmade / Premium', "
        "description = replace(description, 'Handmade carpet', 'Handmade or premium carpet') "
        "WHERE name = 'Karpet Handmade'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE services SET name = 'Karpet Handmade', "
        "description = replace(description, 'Handmade or premium carpet', 'Handmade carpet') "
        "WHERE name = 'Karpet Handmade / Premium'"
    )
