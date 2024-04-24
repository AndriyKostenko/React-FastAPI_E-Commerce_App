"""adding another column friend

Revision ID: 255ef55dda72
Revises: 04604a372cbd
Create Date: 2024-04-24 13:49:04.640515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '255ef55dda72'
down_revision: Union[str, None] = '04604a372cbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('friend', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', "friend")
