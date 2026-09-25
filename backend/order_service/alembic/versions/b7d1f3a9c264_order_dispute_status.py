"""order dispute status

Set while the customer disputes the charge with their bank, then the outcome.

Revision ID: b7d1f3a9c264
Revises: 9e4a7c2d5b18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d1f3a9c264"
down_revision: Union[str, Sequence[str], None] = "9e4a7c2d5b18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("dispute_status", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "dispute_status")
