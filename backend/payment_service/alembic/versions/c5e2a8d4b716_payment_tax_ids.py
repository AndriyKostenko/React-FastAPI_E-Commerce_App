"""payment tax ids

The Stripe Tax calculation an order was priced with, and the sale
transaction recorded from it at capture, which refunds are reversed against.

Revision ID: c5e2a8d4b716
Revises: a3c8e5f2d917
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e2a8d4b716"
down_revision: Union[str, Sequence[str], None] = "a3c8e5f2d917"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("tax_calculation_id", sa.String(), nullable=True))
    op.add_column("payments", sa.Column("tax_transaction_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "tax_transaction_id")
    op.drop_column("payments", "tax_calculation_id")
