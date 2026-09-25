"""payment disputes

Chargebacks Stripe reports on our charges, recorded so the order can be
flagged and an admin can respond before the evidence deadline.

Revision ID: a3c8e5f2d917
Revises: 6b9e2d4f1a83
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3c8e5f2d917"
down_revision: Union[str, Sequence[str], None] = "6b9e2d4f1a83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stripe_dispute_id", sa.String(), nullable=False, unique=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("evidence_due_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_disputes_payment_id", "payment_disputes", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_disputes_payment_id", table_name="payment_disputes")
    op.drop_table("payment_disputes")
