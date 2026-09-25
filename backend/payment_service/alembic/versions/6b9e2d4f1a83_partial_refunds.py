"""partial refunds

Payments can be partly refunded (after capture) or charged less (before
capture). Each requested refund is recorded under order_service's refund id.

Revision ID: 6b9e2d4f1a83
Revises: 52d693f24c4c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6b9e2d4f1a83"
down_revision: Union[str, Sequence[str], None] = "52d693f24c4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("refunded_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("capture_reduction_cents", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "payment_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stripe_refund_id", sa.String(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_refunds_payment_id", "payment_refunds", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_refunds_payment_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")
    op.drop_column("payments", "capture_reduction_cents")
    op.drop_column("payments", "refunded_cents")
