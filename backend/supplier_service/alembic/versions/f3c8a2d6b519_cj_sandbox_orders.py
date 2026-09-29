"""cj sandbox orders

cj_order_attempts.is_sandbox: the CJ order was created with isSandbox=1, so it
is paid with CJ's simulatePay rather than the wallet.

Revision ID: f3c8a2d6b519
Revises: 7a3e5c1b9d42
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3c8a2d6b519"
down_revision: Union[str, Sequence[str], None] = "7a3e5c1b9d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cj_order_attempts",
        sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("cj_order_attempts", "is_sandbox")
