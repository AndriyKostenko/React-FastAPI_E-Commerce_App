"""cj payment lease

Held while one runner takes a CJ order through confirm -> pay, so the
order.confirmed consumer and the payment cron cannot both pay it.

Revision ID: 7a3e5c1b9d42
Revises: e5b21c7d9f60
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a3e5c1b9d42"
down_revision: Union[str, Sequence[str], None] = "e5b21c7d9f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cj_order_attempts",
        sa.Column("payment_leased_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cj_order_attempts", "payment_leased_until")
