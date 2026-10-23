"""cj order attempts: when the customer's details were removed from an ended order

Revision ID: d7a3c5e91b42
Revises: 3c6d68b48411
Create Date: 2026-10-23 21:30:00.000000

CJOrderPersonalDataRetention strips the name, address, phone and email from
an ended order's stored request and clears its email, 90 days after it ended;
this column records that it was done.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a3c5e91b42'
down_revision: Union[str, Sequence[str], None] = '3c6d68b48411'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('cj_order_attempts', sa.Column('personal_data_removed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cj_order_attempts', 'personal_data_removed_at')
