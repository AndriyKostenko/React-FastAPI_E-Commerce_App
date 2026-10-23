"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: 4584df2cd0da
Revises: d4a7e2c9b1f8
Create Date: 2026-10-21 17:51:05.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4584df2cd0da'
down_revision: Union[str, Sequence[str], None] = 'd4a7e2c9b1f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('catalogue_image_mirrors', 'source_url', type_=sa.String(length=2048), existing_type=sa.Text(), existing_nullable=False)
    op.create_check_constraint('ck_catalogue_image_mirrors_counts', 'catalogue_image_mirrors', 'size_bytes >= 0 AND attempts >= 0')
    op.create_check_constraint('ck_inventory_reservations_quantity', 'inventory_reservations', 'quantity > 0')
    op.alter_column('outbox_events', 'event_type', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('outbox_events', 'last_error', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_outbox_events_attempts', 'outbox_events', 'attempts >= 0')
    op.alter_column('product_categories', 'name', type_=sa.String(length=500), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('product_categories', 'cj_category_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_categories', 'image_url', type_=sa.String(length=2048), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_images', 'image_url', type_=sa.String(length=2048), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('product_images', 'image_color', type_=sa.String(length=500), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_images', 'image_color_code', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_reviews', 'comment', type_=sa.String(length=5000), existing_type=sa.String(), existing_nullable=True)
    op.create_unique_constraint('uq_product_review_product_user', 'product_reviews', ['product_id', 'user_id'])
    op.create_check_constraint('ck_product_reviews_rating', 'product_reviews', 'rating >= 0 AND rating <= 5')
    op.alter_column('product_variants', 'vid', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('product_variants', 'variant_key', type_=sa.String(length=500), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_variants', 'variant_name_en', type_=sa.String(length=500), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_variants', 'variant_sku', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_variants', 'barcode', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_variants', 'variant_image', type_=sa.String(length=2048), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('product_variants', 'variant_weight', type_=sa.Numeric(precision=12, scale=3), existing_type=sa.Numeric(), existing_nullable=True)
    op.alter_column('product_variants', 'variant_sell_price', type_=sa.Numeric(precision=12, scale=4), existing_type=sa.Numeric(), existing_nullable=True)
    op.alter_column('product_variants', 'variant_sug_sell_price', type_=sa.Numeric(precision=12, scale=4), existing_type=sa.Numeric(), existing_nullable=True)
    op.create_check_constraint('ck_product_variants_inventory_num', 'product_variants', 'inventory_num >= 0')
    op.create_check_constraint('ck_product_variants_dimensions', 'product_variants', 'variant_weight >= 0 AND variant_length >= 0 AND variant_width >= 0 AND variant_height >= 0')
    op.create_check_constraint('ck_product_variants_prices', 'product_variants', 'variant_sell_price >= 0 AND variant_sug_sell_price >= 0 AND retail_price >= 0')
    op.alter_column('products', 'pid', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('products', 'supplier_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('products', 'supplier_category_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('products', 'name', type_=sa.String(length=200), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('products', 'description', type_=sa.String(length=2000), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('products', 'brand', type_=sa.String(length=50), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('products', 'price', type_=sa.Numeric(precision=10, scale=2), existing_type=sa.Numeric(), existing_nullable=False)
    op.alter_column('products', 'sku', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('products', 'image_url', type_=sa.String(length=2048), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_products_variant_option_names', 'products', 'cardinality(variant_option_names) <= 5')
    op.create_check_constraint('ck_products_quantity', 'products', 'quantity >= 0')
    op.create_check_constraint('ck_products_price', 'products', 'price > 0')
    op.create_check_constraint('ck_supplier_import_batches_errors', 'supplier_import_batches', 'jsonb_array_length(errors) <= 1000')
    op.create_check_constraint('ck_supplier_import_batches_counts', 'supplier_import_batches', 'batch_number >= 1 AND total_batches >= 1 AND imported >= 0 AND updated >= 0 AND failed >= 0')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_supplier_import_batches_counts', 'supplier_import_batches', type_='check')
    op.drop_constraint('ck_supplier_import_batches_errors', 'supplier_import_batches', type_='check')
    op.drop_constraint('ck_products_price', 'products', type_='check')
    op.drop_constraint('ck_products_quantity', 'products', type_='check')
    op.drop_constraint('ck_products_variant_option_names', 'products', type_='check')
    op.alter_column('products', 'image_url', type_=sa.String(), existing_type=sa.String(length=2048), existing_nullable=True)
    op.alter_column('products', 'sku', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('products', 'price', type_=sa.Numeric(), existing_type=sa.Numeric(precision=10, scale=2), existing_nullable=False)
    op.alter_column('products', 'brand', type_=sa.String(), existing_type=sa.String(length=50), existing_nullable=False)
    op.alter_column('products', 'description', type_=sa.String(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('products', 'name', type_=sa.String(), existing_type=sa.String(length=200), existing_nullable=False)
    op.alter_column('products', 'supplier_category_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('products', 'supplier_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('products', 'pid', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.drop_constraint('ck_product_variants_prices', 'product_variants', type_='check')
    op.drop_constraint('ck_product_variants_dimensions', 'product_variants', type_='check')
    op.drop_constraint('ck_product_variants_inventory_num', 'product_variants', type_='check')
    op.alter_column('product_variants', 'variant_sug_sell_price', type_=sa.Numeric(), existing_type=sa.Numeric(precision=12, scale=4), existing_nullable=True)
    op.alter_column('product_variants', 'variant_sell_price', type_=sa.Numeric(), existing_type=sa.Numeric(precision=12, scale=4), existing_nullable=True)
    op.alter_column('product_variants', 'variant_weight', type_=sa.Numeric(), existing_type=sa.Numeric(precision=12, scale=3), existing_nullable=True)
    op.alter_column('product_variants', 'variant_image', type_=sa.String(), existing_type=sa.String(length=2048), existing_nullable=True)
    op.alter_column('product_variants', 'barcode', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('product_variants', 'variant_sku', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('product_variants', 'variant_name_en', type_=sa.String(), existing_type=sa.String(length=500), existing_nullable=True)
    op.alter_column('product_variants', 'variant_key', type_=sa.String(), existing_type=sa.String(length=500), existing_nullable=True)
    op.alter_column('product_variants', 'vid', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=False)
    op.drop_constraint('ck_product_reviews_rating', 'product_reviews', type_='check')
    op.drop_constraint('uq_product_review_product_user', 'product_reviews', type_='unique')
    op.alter_column('product_reviews', 'comment', type_=sa.String(), existing_type=sa.String(length=5000), existing_nullable=True)
    op.alter_column('product_images', 'image_color_code', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=True)
    op.alter_column('product_images', 'image_color', type_=sa.String(), existing_type=sa.String(length=500), existing_nullable=True)
    op.alter_column('product_images', 'image_url', type_=sa.String(), existing_type=sa.String(length=2048), existing_nullable=False)
    op.alter_column('product_categories', 'image_url', type_=sa.String(), existing_type=sa.String(length=2048), existing_nullable=True)
    op.alter_column('product_categories', 'cj_category_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('product_categories', 'name', type_=sa.String(), existing_type=sa.String(length=500), existing_nullable=False)
    op.drop_constraint('ck_outbox_events_attempts', 'outbox_events', type_='check')
    op.alter_column('outbox_events', 'last_error', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('outbox_events', 'event_type', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
    op.drop_constraint('ck_inventory_reservations_quantity', 'inventory_reservations', type_='check')
    op.drop_constraint('ck_catalogue_image_mirrors_counts', 'catalogue_image_mirrors', type_='check')
    op.alter_column('catalogue_image_mirrors', 'source_url', type_=sa.Text(), existing_type=sa.String(length=2048), existing_nullable=False)
