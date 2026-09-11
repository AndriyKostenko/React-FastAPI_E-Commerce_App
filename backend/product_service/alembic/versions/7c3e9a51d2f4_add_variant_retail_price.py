"""add variant retail price and re-price supplier products in CAD

Supplier products used to be listed and quoted straight from CJ's USD
numbers, labelled CAD. This revision adds the stored CAD shelf price and
backfills it, plus the listing price, through the same
``SupplierRetailPricing`` rule the importer uses, so existing rows are
sellable without waiting for the next catalog sync.

Downgrade drops the column only; listing prices keep their CAD values.

Revision ID: 7c3e9a51d2f4
Revises: 1ee7bfc89e7e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from shared.settings import get_settings
from shared.utils.supplier_pricing import SupplierRetailPricing


revision: str = "7c3e9a51d2f4"
down_revision: Union[str, Sequence[str], None] = "1ee7bfc89e7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRICE = sa.bindparam("price", type_=sa.Numeric(10, 2))
UPDATE_VARIANT = sa.text(
    "UPDATE product_variants SET retail_price = :price WHERE id = :id"
).bindparams(PRICE)
UPDATE_PRODUCT = sa.text("UPDATE products SET price = :price WHERE id = :id").bindparams(PRICE)


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("retail_price", sa.Numeric(10, 2), nullable=True),
    )
    _backfill(op.get_bind(), SupplierRetailPricing.from_settings(get_settings()))


def _backfill(connection: sa.Connection, pricing: SupplierRetailPricing) -> None:
    variants = connection.execute(
        sa.text(
            """
            SELECT v.id, v.product_id, v.variant_sell_price, v.variant_sug_sell_price
            FROM product_variants v
            JOIN products p ON p.id = v.product_id
            WHERE p.supplier_id IS NOT NULL
            """
        )
    ).all()

    cheapest_by_product = {}
    for variant_id, product_id, cost, suggested in variants:
        retail = pricing.retail_price_cad(cost_usd=cost, suggested_usd=suggested)
        if retail is None:
            continue
        connection.execute(UPDATE_VARIANT, {"price": retail, "id": variant_id})
        current = cheapest_by_product.get(product_id)
        if current is None or retail < current:
            cheapest_by_product[product_id] = retail

    products = connection.execute(
        sa.text("SELECT id, price FROM products WHERE supplier_id IS NOT NULL")
    ).all()
    for product_id, cost in products:
        price = cheapest_by_product.get(product_id) or pricing.retail_price_cad(cost_usd=cost)
        if price is None:
            continue
        connection.execute(UPDATE_PRODUCT, {"price": price, "id": product_id})


def downgrade() -> None:
    op.drop_column("product_variants", "retail_price")
