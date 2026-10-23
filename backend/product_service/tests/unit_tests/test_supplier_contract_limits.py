"""What supplier-service sends is bounded: a raw description is clipped, everything else refused past a bound."""
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts.limits import COUNT_MAX, IMAGES_MAX, SUPPLIER_TEXT_MAX_LENGTH, VARIANTS_MAX
from contracts.supplier import GenericSupplierProduct, SupplierStockKey, SupplierStockLevel
from service_layer.supplier_product_mapper import SupplierProductMapper
from utils.supplier_pricing import SupplierRetailPricing

PRICING = SupplierRetailPricing(usd_to_cad_rate=Decimal("1.40"), markup_multiplier=Decimal("2.00"))


def _product(**overrides) -> GenericSupplierProduct:
    return GenericSupplierProduct(
        supplier_id="cjdropshipping", supplier_pid="p1", name="Shirt", price=Decimal("10.00"), **overrides
    )


class TestSupplierProducts:
    def test_an_oversized_html_description_is_clipped_and_still_imports(self):
        # CJ descriptions are HTML of any length; one past the bound must not lose the product.
        html = "<p>Soft cotton</p>" * (SUPPLIER_TEXT_MAX_LENGTH // 10)
        product = _product(description=html)

        assert len(product.description) == SUPPLIER_TEXT_MAX_LENGTH
        create = SupplierProductMapper.map_supplier_product(product, uuid4(), PRICING)
        assert create.description.startswith("Soft cotton Soft cotton")
        assert len(create.description) <= SupplierProductMapper.DESCRIPTION_MAX_LENGTH

    def test_more_images_than_a_product_page_shows_are_refused(self):
        with pytest.raises(ValidationError, match="images"):
            _product(images=[f"https://cf.cjdropshipping.com/{index}.jpg" for index in range(IMAGES_MAX + 1)])

    def test_a_product_at_every_bound_round_trips(self):
        product = _product(images=["https://cf.cjdropshipping.com/a.jpg"] * IMAGES_MAX)

        assert len(GenericSupplierProduct.model_validate_json(product.model_dump_json()).images) == IMAGES_MAX


class TestStockLevels:
    def test_more_variant_ids_than_any_product_has_are_refused(self):
        with pytest.raises(ValidationError, match="vids"):
            SupplierStockKey(supplier_pid="p1", vids=[f"v{index}" for index in range(VARIANTS_MAX + 1)])

    def test_a_stock_level_past_any_real_count_is_refused(self):
        with pytest.raises(ValidationError, match=f"stock cannot be above {COUNT_MAX}"):
            SupplierStockLevel(supplier_pid="p1", variants={"v1": COUNT_MAX + 1})

    def test_negative_stock_is_still_refused(self):
        with pytest.raises(ValidationError, match="stock cannot be negative"):
            SupplierStockLevel(supplier_pid="p1", variants={"v1": -1})
