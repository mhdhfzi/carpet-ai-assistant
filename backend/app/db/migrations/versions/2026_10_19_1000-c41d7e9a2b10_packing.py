"""packing: who washed and packed each item, gulung/lipat for velvet, untagged carpets

Revision ID: c41d7e9a2b10
Revises: b57123a68239
Create Date: 2026-10-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c41d7e9a2b10"
down_revision: str | Sequence[str] | None = "b57123a68239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "services",
        sa.Column("needs_fold", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("order_items", sa.Column("washed_by_id", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("packed_by_id", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("wash_note", sa.Text(), nullable=True))
    op.add_column(
        "order_items",
        sa.Column(
            "fold",
            sa.Enum(
                "rolled",
                "folded",
                name="item_fold",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_order_items_washed_by_id_owners"),
        "order_items",
        "owners",
        ["washed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_order_items_packed_by_id_owners"),
        "order_items",
        "owners",
        ["packed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "untagged_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("found_on", sa.Date(), nullable=False),
        sa.Column("found_by_id", sa.Integer(), nullable=True),
        sa.Column("matched_tag", sa.String(length=20), nullable=True),
        sa.Column("matched_by_id", sa.Integer(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["found_by_id"],
            ["owners.id"],
            name=op.f("fk_untagged_items_found_by_id_owners"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["matched_by_id"],
            ["owners.id"],
            name=op.f("fk_untagged_items_matched_by_id_owners"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_untagged_items")),
    )
    # Velvet carpets are packed rolled or folded (the packing form asks which).
    op.execute("UPDATE services SET needs_fold = true WHERE name ILIKE '%velvet%'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("untagged_items")
    op.drop_constraint(
        op.f("fk_order_items_packed_by_id_owners"), "order_items", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_order_items_washed_by_id_owners"), "order_items", type_="foreignkey"
    )
    op.drop_column("order_items", "fold")
    op.drop_column("order_items", "wash_note")
    op.drop_column("order_items", "packed_by_id")
    op.drop_column("order_items", "washed_by_id")
    op.drop_column("services", "needs_fold")
