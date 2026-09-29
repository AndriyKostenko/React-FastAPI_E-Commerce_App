"""product stock checked at

products.stock_checked_at: when the supplier stock behind products.quantity
was measured by the hourly CJ refresh; older measurements are ignored.

Revision ID: 9b4d2e7f1a63
Revises: 7c3e9a51d2f4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b4d2e7f1a63"
down_revision: Union[str, Sequence[str], None] = "7c3e9a51d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("stock_checked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "stock_checked_at")
