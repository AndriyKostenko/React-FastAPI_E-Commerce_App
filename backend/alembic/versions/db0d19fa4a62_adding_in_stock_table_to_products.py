"""adding in_stock table to products

Revision ID: db0d19fa4a62
Revises: 1b83ebbdb38b
Create Date: 2024-05-15 19:48:01.154069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db0d19fa4a62'
down_revision: Union[str, None] = '1b83ebbdb38b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('in_stock', sa.Boolean, nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'in_stock')
