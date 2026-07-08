"""add_product_pid_and_variants

Revision ID: 428dadc5871e
Revises: a1b2c3d4e5f6
Create Date: 2026-07-07 12:07:22.533045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '428dadc5871e'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the product variants table
    op.create_table('product_variants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('vid', sa.String(), nullable=False),
    sa.Column('variant_key', sa.String(), nullable=True),
    sa.Column('variant_name_en', sa.String(), nullable=True),
    sa.Column('variant_sku', sa.String(), nullable=True),
    sa.Column('barcode', sa.String(), nullable=True),
    sa.Column('variant_image', sa.String(), nullable=True),
    sa.Column('variant_weight', sa.Numeric(), nullable=True),
    sa.Column('variant_length', sa.Integer(), nullable=True),
    sa.Column('variant_width', sa.Integer(), nullable=True),
    sa.Column('variant_height', sa.Integer(), nullable=True),
    sa.Column('variant_sell_price', sa.Numeric(), nullable=True),
    sa.Column('variant_sug_sell_price', sa.Numeric(), nullable=True),
    sa.Column('inventory_num', sa.Integer(), nullable=True),
    sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'vid', name='uq_product_variant_product_id_vid')
    )
    op.create_index('idx_product_variant_product_id', 'product_variants', ['product_id'], unique=False)
    op.create_index('idx_product_variant_vid', 'product_variants', ['vid'], unique=False)

    # Add CJ Dropshipping columns to products
    op.add_column('products', sa.Column('pid', sa.String(), nullable=True))
    op.add_column('products', sa.Column('sku', sa.String(), nullable=True))
    op.add_column('products', sa.Column('image_url', sa.String(), nullable=True))
    op.create_index('idx_product_pid', 'products', ['pid'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_product_pid', table_name='products')
    op.drop_column('products', 'image_url')
    op.drop_column('products', 'sku')
    op.drop_column('products', 'pid')

    op.drop_index('idx_product_variant_vid', table_name='product_variants')
    op.drop_index('idx_product_variant_product_id', table_name='product_variants')
    op.drop_table('product_variants')
