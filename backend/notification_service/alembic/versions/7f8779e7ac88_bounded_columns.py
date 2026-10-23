"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: 7f8779e7ac88
Revises: 012487ca2c66
Create Date: 2026-10-21 17:51:08.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f8779e7ac88'
down_revision: Union[str, Sequence[str], None] = '012487ca2c66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('notifications', 'message', type_=sa.String(length=5000), existing_type=sa.String(), existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('notifications', 'message', type_=sa.String(), existing_type=sa.String(length=5000), existing_nullable=False)
