"""house jobs: sofa, mattress and car seats are done at the customer's home

Revision ID: e5b9c03d7a21
Revises: d2a8f61c3e57
Create Date: 2026-10-20 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b9c03d7a21"
down_revision: str | Sequence[str] | None = "d2a8f61c3e57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "services", sa.Column("on_site", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("orders", sa.Column("visit_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_orders_visit_at"), "orders", ["visit_at"], unique=False)
    # Everything not priced per square foot (sofa, mattress, car seats) is done at home.
    op.execute("UPDATE services SET on_site = true WHERE pricing_unit <> 'per_sqft'")
    # Home jobs have no washing step: one marked washed counts as done.
    op.execute(
        "UPDATE order_items i SET status = 'ready', "
        "ready_on = COALESCE(i.ready_on, i.washed_on), "
        "packed_by_id = COALESCE(i.packed_by_id, i.washed_by_id), "
        "washed_on = NULL, washed_by_id = NULL, wash_note = NULL "
        "FROM services s WHERE s.id = i.service_id AND s.on_site AND i.status = 'washed'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_orders_visit_at"), table_name="orders")
    op.drop_column("orders", "visit_at")
    op.drop_column("services", "on_site")
