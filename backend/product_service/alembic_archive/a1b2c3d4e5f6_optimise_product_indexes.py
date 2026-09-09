"""optimise_product_indexes

Drops low-value single-column indexes and adds composite + partial indexes
that match the real query patterns:
  - products/detailed?limit=50  → in_stock filter + date_created ORDER BY
  - browse by category, in-stock only
  - browse by brand, in-stock only
  - price range queries
  - avg-rating aggregation per product

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── products: drop low-value single-column date indexes ─────────────────
    # date_created / date_updated are now covered by composite indexes below
    op.drop_index('idx_product_date_created', table_name='products', if_exists=True)
    op.drop_index('idx_product_date_updated', table_name='products', if_exists=True)

    # ── products: add price index for range queries ──────────────────────────
    op.create_index('idx_product_price', 'products', ['price'])

    # ── products: composite indexes for common query patterns ────────────────
    # default browse query: WHERE in_stock = true ORDER BY date_created DESC
    op.create_index('idx_product_in_stock_date_created', 'products', ['in_stock', 'date_created'])
    # category browse, in-stock only
    op.create_index('idx_product_category_in_stock', 'products', ['category_id', 'in_stock'])
    # brand browse, in-stock only
    op.create_index('idx_product_brand_in_stock', 'products', ['brand', 'in_stock'])
    # price sort within category
    op.create_index('idx_product_category_price', 'products', ['category_id', 'price'])

    # ── products: partial index — only in-stock rows ─────────────────────────
    # Much smaller than a full index; Postgres auto-selects it for WHERE in_stock = true
    op.create_index(
        'idx_product_in_stock_partial',
        'products', ['id', 'date_created'],
        postgresql_where='in_stock = true',
    )

    # ── product_categories: drop useless date/image_url indexes ─────────────
    op.drop_index('idx_product_categories_date_created', table_name='product_categories', if_exists=True)
    op.drop_index('idx_product_categories_image_url',   table_name='product_categories', if_exists=True)

    # ── product_images: drop low-value date indexes ──────────────────────────
    op.drop_index('idx_product_image_date_created', table_name='product_images', if_exists=True)
    op.drop_index('idx_product_image_date_updated', table_name='product_images', if_exists=True)

    # ── product_reviews: add composite (product_id, rating) for avg agg ─────
    op.create_index('idx_product_review_product_rating', 'product_reviews', ['product_id', 'rating'])


def downgrade() -> None:
    # restore old single-column indexes
    op.drop_index('idx_product_review_product_rating',  table_name='product_reviews')

    op.create_index('idx_product_image_date_updated', 'product_images', ['date_updated'])
    op.create_index('idx_product_image_date_created', 'product_images', ['date_created'])

    op.create_index('idx_product_categories_image_url',   'product_categories', ['image_url'])
    op.create_index('idx_product_categories_date_created', 'product_categories', ['date_created'])

    op.drop_index('idx_product_in_stock_partial',       table_name='products')
    op.drop_index('idx_product_category_price',         table_name='products')
    op.drop_index('idx_product_brand_in_stock',         table_name='products')
    op.drop_index('idx_product_category_in_stock',      table_name='products')
    op.drop_index('idx_product_in_stock_date_created',  table_name='products')
    op.drop_index('idx_product_price',                  table_name='products')

    op.create_index('idx_product_date_updated', 'products', ['date_updated'])
    op.create_index('idx_product_date_created', 'products', ['date_created'])
