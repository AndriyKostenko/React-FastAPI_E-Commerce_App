"""supplier image reviews: a vision model's verdict on each supplier product photo

Revision ID: 7c2e9a4d1b36
Revises: 4584df2cd0da
Create Date: 2026-10-22 18:00:00.000000

One row per (supplier, product, photo URL): the import reviews a photo once
and reuses the verdict, and the approved description, on every later sync.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7c2e9a4d1b36'
down_revision: Union[str, Sequence[str], None] = '4584df2cd0da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'supplier_image_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('supplier_id', sa.String(length=255), nullable=False),
        sa.Column('pid', sa.String(length=255), nullable=False),
        sa.Column('image_url', sa.String(length=2048), nullable=False),
        sa.Column('verdict', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("verdict IN ('approved', 'rejected')", name='ck_supplier_image_reviews_verdict'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('supplier_id', 'pid', 'image_url', name='uq_supplier_image_reviews_photo'),
    )
    op.create_index('idx_supplier_image_reviews_product', 'supplier_image_reviews', ['supplier_id', 'pid'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_supplier_image_reviews_product', table_name='supplier_image_reviews')
    op.drop_table('supplier_image_reviews')
