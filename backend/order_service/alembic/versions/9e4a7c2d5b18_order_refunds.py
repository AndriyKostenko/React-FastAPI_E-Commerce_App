"""order refunds

Partial refunds of an order: chosen lines, maybe shipping. Each row's id is the
Stripe idempotency key payment-service refunds under.

Revision ID: 9e4a7c2d5b18
Revises: 8d2f6a1c3e57
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9e4a7c2d5b18"
down_revision: Union[str, Sequence[str], None] = "8d2f6a1c3e57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("includes_shipping", sa.Boolean(), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_order_refunds_order_id", "order_refunds", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_refunds_order_id", table_name="order_refunds")
    op.drop_table("order_refunds")
