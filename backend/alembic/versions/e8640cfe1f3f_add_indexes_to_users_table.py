"""Add indexes to users table

Revision ID: e8640cfe1f3f
Revises: db0d19fa4a62
Create Date: 2025-04-22 21:14:22.604717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8640cfe1f3f'
down_revision: Union[str, None] = 'db0d19fa4a62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('idx_users_date_created', 'users', ['date_created'], unique=False)
    op.create_index('idx_users_email', 'users', ['email'], unique=False)
    op.create_index('idx_users_is_active', 'users', ['is_active'], unique=False)
    op.create_index('idx_users_is_verified', 'users', ['is_verified'], unique=False)
    op.create_index('idx_users_role', 'users', ['role'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_is_verified', table_name='users')
    op.drop_index('idx_users_is_active', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_date_created', table_name='users')
    # ### end Alembic commands ###
