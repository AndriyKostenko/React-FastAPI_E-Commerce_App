"""saga confirmed_at

When an order's payment and inventory both cleared. The sweep that cancels
confirmed orders CJ never took on measures its 24 hours from here.

Revision ID: 4c1d7e9a2b50
Revises: 3d8b6f0e2a91
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c1d7e9a2b50"
down_revision: Union[str, Sequence[str], None] = "3d8b6f0e2a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_saga_states",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_saga_states", "confirmed_at")
