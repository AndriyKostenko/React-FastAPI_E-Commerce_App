"""generated designs: each stored design and who made it, for retention

Revision ID: c4e8b2a7d913
Revises: a91d3f6c2b58
Create Date: 2026-10-23 21:00:00.000000

The retention job deletes a design no order holds once it is old enough, and
a deleted account's unordered designs go with it; the stored object alone
says neither its age nor its owner. Designs stored before this have no row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4e8b2a7d913'
down_revision: Union[str, Sequence[str], None] = 'a91d3f6c2b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'generated_designs',
        sa.Column('key', sa.String(length=512), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_index('idx_generated_designs_user', 'generated_designs', ['user_id'], unique=False)
    op.create_index('idx_generated_designs_created', 'generated_designs', ['date_created'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_generated_designs_created', table_name='generated_designs')
    op.drop_index('idx_generated_designs_user', table_name='generated_designs')
    op.drop_table('generated_designs')
