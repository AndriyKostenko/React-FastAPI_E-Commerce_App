"""order amount breakdown and chosen shipping

The order total now includes shipping (and, later, tax). These columns record
how the total was built and which CJ logistics option the customer paid for,
so fulfillment ships with that option and can compare CJ's bill to its quote.

Revision ID: 3d8b6f0e2a91
Revises: e2c74b1a8f36
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d8b6f0e2a91"
down_revision: Union[str, Sequence[str], None] = "e2c74b1a8f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MONEY_COLUMNS = ("subtotal_amount", "shipping_amount", "tax_amount", "shipping_cost_usd")


def upgrade() -> None:
    for name in _MONEY_COLUMNS:
        op.add_column("orders", sa.Column(name, sa.Numeric(10, 2), nullable=True))
    op.add_column("orders", sa.Column("shipping_logistic_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "shipping_logistic_name")
    for name in reversed(_MONEY_COLUMNS):
        op.drop_column("orders", name)
