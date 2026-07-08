"""Unit tests for mapping generic supplier products to product_service CreateProduct."""
from decimal import Decimal
from uuid import uuid4

import pytest

from service_layer.supplier_product_mapper import SupplierProductMapper
from shared.schemas.supplier_schemas import GenericSupplierProduct, SupplierProductVariant
from shared.schemas.product_schemas import CreateProduct


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
            category_id="cat-123",
            variants=[
                SupplierProductVariant(
                    vid="v1",
                    variant_key="S",
                    variant_name_en="Small",
                    variant_sell_price=Decimal("12.34"),
                )
            ],
        )

        create_product = SupplierProductMapper.map_supplier_product(supplier_product)

        assert isinstance(create_product, CreateProduct)
        assert create_product.pid == "p123"
        assert create_product.name == "test t-shirt"
        assert create_product.description == "A nice shirt"
        assert create_product.price == Decimal("12.34")
        assert create_product.quantity == 5
        assert create_product.in_stock is True
        assert create_product.category_id == "cat-123"
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

        result = SupplierProductMapper.map_supplier_products(products)

        assert len(result) == 2
        assert result[0].pid == "p1"
        assert result[1].pid == "p2"
        assert result[1].in_stock is False
