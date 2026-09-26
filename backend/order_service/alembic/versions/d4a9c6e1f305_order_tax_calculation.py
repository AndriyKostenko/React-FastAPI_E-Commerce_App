"""order tax calculation

orders.tax_calculation_id: the Stripe Tax calculation behind orders.tax_amount.
order_refunds.tax_amount: the share of the order's tax a refund gives back.

Revision ID: d4a9c6e1f305
Revises: b7d1f3a9c264
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a9c6e1f305"
down_revision: Union[str, Sequence[str], None] = "b7d1f3a9c264"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("tax_calculation_id", sa.String(), nullable=True))
    op.add_column(
        "order_refunds",
        sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("order_refunds", "tax_amount")
    op.drop_column("orders", "tax_calculation_id")
