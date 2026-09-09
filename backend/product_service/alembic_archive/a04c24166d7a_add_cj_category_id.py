"""add_cj_category_id

Revision ID: a04c24166d7a
Revises: 428dadc5871e
Create Date: 2026-07-07 12:15:02.064241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a04c24166d7a'
down_revision: Union[str, Sequence[str], None] = '428dadc5871e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('product_categories', sa.Column('cj_category_id', sa.String(), nullable=True))
    op.create_index('idx_product_categories_cj_id', 'product_categories', ['cj_category_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_product_categories_cj_id', table_name='product_categories')
    op.drop_column('product_categories', 'cj_category_id')
