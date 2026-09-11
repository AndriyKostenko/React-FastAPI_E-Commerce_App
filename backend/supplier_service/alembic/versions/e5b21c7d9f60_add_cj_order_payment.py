"""add cj order payment columns

CJ orders used to be created with payType=3 and then never confirmed or paid,
so CJ never shipped them. Payment now runs as recorded steps after creation;
these columns hold what CJ billed, the most it may bill before a human reviews
it, when it was paid, and how many attempts it took.

Revision ID: e5b21c7d9f60
Revises: c4a7f1d2e9b8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b21c7d9f60"
down_revision: Union[str, Sequence[str], None] = "c4a7f1d2e9b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "cj_order_attempts"
PAYMENT_INDEX = "idx_cj_order_attempt_payment_due"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("cj_order_amount_usd", sa.Numeric(10, 2), nullable=True))
    op.add_column(TABLE, sa.Column("expected_max_amount_usd", sa.Numeric(10, 2), nullable=True))
    op.add_column(TABLE, sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        TABLE,
        sa.Column("payment_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(PAYMENT_INDEX, TABLE, ["status", "date_updated"])


def downgrade() -> None:
    op.drop_index(PAYMENT_INDEX, table_name=TABLE)
    op.drop_column(TABLE, "payment_attempts")
    op.drop_column(TABLE, "paid_at")
    op.drop_column(TABLE, "expected_max_amount_usd")
    op.drop_column(TABLE, "cj_order_amount_usd")
