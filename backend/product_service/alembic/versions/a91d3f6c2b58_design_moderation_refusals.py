"""design moderation refusals: customer designs the moderation check refused

Revision ID: a91d3f6c2b58
Revises: 7c2e9a4d1b36
Create Date: 2026-10-23 18:00:00.000000

One row per refused generation (what was asked for, at which check, which
rule and why), shown to the admins. The refused image is never stored.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a91d3f6c2b58'
down_revision: Union[str, Sequence[str], None] = '7c2e9a4d1b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'design_moderation_refusals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('stage', sa.String(length=16), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('prompt', sa.String(length=1000), nullable=False),
        sa.Column('style', sa.String(length=100), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("stage IN ('prompt', 'image')", name='ck_design_moderation_refusals_stage'),
        sa.CheckConstraint(
            "category IN ('sexual', 'hate', 'violence', 'drugs', 'brand', 'character', 'real_person')",
            name='ck_design_moderation_refusals_category',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_design_moderation_refusals_user', 'design_moderation_refusals', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_design_moderation_refusals_user', table_name='design_moderation_refusals')
    op.drop_table('design_moderation_refusals')
