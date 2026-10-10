"""cj stock subscriptions

cj_stock_subscriptions: each CJ product we sell and when CJ accepted its
stock-push subscription. cj_stock_subscription_variants: variant id -> product
id, because a STOCK push names variants only.

Revision ID: b8e3f1a6c274
Revises: a6d4e2f8c135
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e3f1a6c274"
down_revision: Union[str, Sequence[str], None] = "a6d4e2f8c135"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cj_stock_subscriptions",
        sa.Column("pid", sa.String(length=64), nullable=False),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("date_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("pid"),
    )
    op.create_table(
        "cj_stock_subscription_variants",
        sa.Column("vid", sa.String(length=64), nullable=False),
        sa.Column("pid", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["pid"], ["cj_stock_subscriptions.pid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vid"),
    )
    op.create_index(
        "idx_cj_stock_subscription_variants_pid", "cj_stock_subscription_variants", ["pid"]
    )


def downgrade() -> None:
    op.drop_index("idx_cj_stock_subscription_variants_pid", table_name="cj_stock_subscription_variants")
    op.drop_table("cj_stock_subscription_variants")
    op.drop_table("cj_stock_subscriptions")
