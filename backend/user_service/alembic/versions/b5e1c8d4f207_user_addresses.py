"""user addresses: the customer's saved shipping addresses

Revision ID: b5e1c8d4f207
Revises: a3d7f2c9e614
Create Date: 2026-10-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e1c8d4f207'
down_revision: Union[str, Sequence[str], None] = 'a3d7f2c9e614'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_addresses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('street', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('province', sa.String(length=2), nullable=False),
    sa.Column('postal_code', sa.String(length=7), nullable=False),
    sa.Column('country', sa.String(length=64), nullable=False),
    sa.Column('country_code', sa.String(length=2), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_addresses_user_id', 'user_addresses', ['user_id'], unique=False)
    op.create_index(
        'uq_user_addresses_one_default', 'user_addresses', ['user_id'],
        unique=True, postgresql_where=sa.text('is_default'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_user_addresses_one_default', table_name='user_addresses')
    op.drop_index('idx_user_addresses_user_id', table_name='user_addresses')
    op.drop_table('user_addresses')
