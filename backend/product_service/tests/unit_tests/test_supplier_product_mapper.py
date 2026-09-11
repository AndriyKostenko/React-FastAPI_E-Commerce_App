"""Unit tests for mapping generic supplier products to product_service CreateProduct."""
from decimal import Decimal
from uuid import uuid4

import pytest

from service_layer.supplier_product_mapper import SupplierProductMapper
from shared.contracts.supplier import GenericSupplierProduct, SupplierProductVariant
from shared.utils.supplier_pricing import SupplierRetailPricing
from schemas.product_schemas import CreateProduct


PRICING = SupplierRetailPricing(
    usd_to_cad_rate=Decimal("1.40"), markup_multiplier=Decimal("2.00")
)


class TestSupplierProductMapper:
    def test_maps_generic_supplier_product(self) -> None:
        supplier_product = GenericSupplierProduct(
            supplier_id="cjdropshipping",
            supplier_pid="p123",
            name="Test T-Shirt",
            description="A nice shirt",
            sku="SKU123",
            brand="cjdropshipping",
            price=Decimal("12.34"),
            quantity=5,
            in_stock=True,
            image_url="https://example.com/image.jpg",
            images=["https://example.com/image2.jpg"],
            supplier_category_id="cat-123",
            variants=[
                SupplierProductVariant(
                    vid="v1",
                    variant_key="S",
                    variant_name_en="Small",
                    variant_sell_price=Decimal("12.34"),
                )
            ],
        )

        local_category_id = uuid4()
        create_product = SupplierProductMapper.map_supplier_product(
            supplier_product,
            local_category_id,
            PRICING,
        )

        assert isinstance(create_product, CreateProduct)
        assert create_product.pid == "p123"
        assert create_product.name == "test t-shirt"
        assert create_product.description == "A nice shirt"
        # 12.34 USD cost x 2.00 markup x 1.40 FX = 34.55 CAD, shelved at 34.99.
        assert create_product.price == Decimal("34.99")
        assert create_product.variants[0].retail_price == Decimal("34.99")
        assert create_product.variants[0].variant_sell_price == Decimal("12.34")
        assert create_product.quantity == 5
        assert create_product.in_stock is True
        assert create_product.category_id == local_category_id
        assert create_product.supplier_category_id == "cat-123"
        assert len(create_product.images) == 1
        assert len(create_product.variants) == 1
        assert create_product.variants[0].vid == "v1"

    def test_maps_multiple_products(self) -> None:
        products = [
            GenericSupplierProduct(
                supplier_id="cjdropshipping",
                supplier_pid="p1",
                name="Product 1",
                price=Decimal("1.00"),
                quantity=1,
                in_stock=True,
            ),
            GenericSupplierProduct(
                supplier_id="cjdropshipping",
                supplier_pid="p2",
                name="Product 2",
                price=Decimal("2.00"),
                quantity=0,
                in_stock=False,
            ),
        ]

        result = SupplierProductMapper.map_supplier_products(products, uuid4(), PRICING)

        assert len(result) == 2
        assert result[0].pid == "p1"
        assert result[1].pid == "p2"
        assert result[1].in_stock is False

    def test_preserves_high_supplier_inventory(self) -> None:
        supplier_product = GenericSupplierProduct(
            supplier_id="cjdropshipping",
            supplier_pid="high-stock",
            name="High Stock T-Shirt",
            price=Decimal("10.00"),
            quantity=3_960_000,
            in_stock=True,
        )

        result = SupplierProductMapper.map_supplier_product(
            supplier_product,
            uuid4(),
            PRICING,
        )

        assert result.quantity == 3_960_000
        assert result.in_stock is True

    def test_normalizes_and_bounds_supplier_html_description(self) -> None:
        supplier_product = GenericSupplierProduct(
            supplier_id="cjdropshipping",
            supplier_pid="p-html",
            name="HTML Product",
            description=f"<p>Product&nbsp;details</p><div>{'x' * 2500}</div>",
            price=Decimal("10.00"),
        )

        result = SupplierProductMapper.map_supplier_product(
            supplier_product,
            uuid4(),
            PRICING,
        )

        assert result.description.startswith("Product details ")
        assert "<p>" not in result.description
        assert "&nbsp;" not in result.description
        assert len(result.description) == 2000

    def test_listing_price_is_cheapest_variant_retail_price(self) -> None:
        supplier_product = GenericSupplierProduct(
            supplier_id="cjdropshipping",
            supplier_pid="p-variants",
            name="Variant Shirt",
            price=Decimal("5.00"),
            variants=[
                SupplierProductVariant(vid="big", variant_sell_price=Decimal("9.00")),
                SupplierProductVariant(
                    vid="small",
                    variant_sell_price=Decimal("6.00"),
                    variant_sug_sell_price=Decimal("20.00"),
                ),
            ],
        )

        result = SupplierProductMapper.map_supplier_product(
            supplier_product, uuid4(), PRICING
        )

        retail = {variant.vid: variant.retail_price for variant in result.variants}
        # big: 9.00 x 2 x 1.40 = 25.20 -> 25.99; small: suggested 20.00 x 1.40 = 28.00 -> 28.99
        assert retail == {"big": Decimal("25.99"), "small": Decimal("28.99")}
        assert result.price == Decimal("25.99")

    def test_rejects_product_without_any_price(self) -> None:
        supplier_product = GenericSupplierProduct(
            supplier_id="cjdropshipping",
            supplier_pid="p-free",
            name="Unpriced Shirt",
            price=Decimal("0"),
        )

        with pytest.raises(ValueError, match="no usable price"):
            SupplierProductMapper.map_supplier_product(
                supplier_product, uuid4(), PRICING
            )
