"""adding an image table to db users

Revision ID: 1b83ebbdb38b
Revises: 255ef55dda72
Create Date: 2024-05-02 19:32:44.886757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b83ebbdb38b'
down_revision: Union[str, None] = '255ef55dda72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('image', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'image')
