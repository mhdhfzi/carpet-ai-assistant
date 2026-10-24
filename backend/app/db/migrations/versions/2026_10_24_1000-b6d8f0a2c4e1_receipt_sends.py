"""receipt sends: each time a worker confirms a receipt went to the customer

Revision ID: b6d8f0a2c4e1
Revises: a3c5e7f9b1d2
Create Date: 2026-10-24 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6d8f0a2c4e1"
down_revision: str | Sequence[str] | None = "a3c5e7f9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "receipt_sends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "whatsapp",
                "image",
                "pdf",
                name="receipt_channel",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_receipt_sends_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sent_by_id"],
            ["owners.id"],
            name=op.f("fk_receipt_sends_sent_by_id_owners"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receipt_sends")),
    )
    op.create_index(op.f("ix_receipt_sends_order_id"), "receipt_sends", ["order_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_receipt_sends_order_id"), table_name="receipt_sends")
    op.drop_table("receipt_sends")
