"""cj order cancelled_at

cj_order_attempts.cancelled_at: the local order was cancelled. Set by the
order.cancelled consumer whatever state the attempt is in (a row is created
when there is none yet), so an order.confirmed handled afterwards, or while
the CJ order is being created, never leaves a CJ order to be paid for.

Revision ID: a6d4e2f8c135
Revises: f3c8a2d6b519
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6d4e2f8c135"
down_revision: Union[str, Sequence[str], None] = "f3c8a2d6b519"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cj_order_attempts",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cj_order_attempts", "cancelled_at")
