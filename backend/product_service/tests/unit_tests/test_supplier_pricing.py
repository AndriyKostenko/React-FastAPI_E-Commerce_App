"""Unit tests for the shared supplier retail pricing rule."""
from decimal import Decimal

import pytest

from shared.utils.supplier_pricing import SupplierRetailPricing


@pytest.fixture
def pricing() -> SupplierRetailPricing:
    return SupplierRetailPricing(
        usd_to_cad_rate=Decimal("1.40"), markup_multiplier=Decimal("2.00")
    )


class TestRetailPriceCad:
    def test_cost_times_markup_is_the_floor(self, pricing: SupplierRetailPricing) -> None:
        # 10.00 x 2 x 1.40 = 28.00 CAD; a lower suggestion does not undercut it.
        price = pricing.retail_price_cad(Decimal("10.00"), Decimal("12.00"))
        assert price == Decimal("28.99")

    def test_higher_suggested_price_wins(self, pricing: SupplierRetailPricing) -> None:
        # 30.00 x 1.40 = 42.00 CAD beats the 28.00 CAD floor.
        price = pricing.retail_price_cad(Decimal("10.00"), Decimal("30.00"))
        assert price == Decimal("42.99")

    def test_suggested_price_alone_is_converted(self, pricing: SupplierRetailPricing) -> None:
        assert pricing.retail_price_cad(None, Decimal("7.10")) == Decimal("9.99")

    def test_price_never_undercuts_the_computed_amount(
        self, pricing: SupplierRetailPricing
    ) -> None:
        # 8.56 x 2 x 1.40 = 23.968 CAD rounds up to 23.99, not down.
        price = pricing.retail_price_cad(Decimal("8.56"))
        assert price == Decimal("23.99")
        assert price >= Decimal("8.56") * 2 * Decimal("1.40")

    @pytest.mark.parametrize("cost, suggested", [(None, None), (Decimal("0"), Decimal("-1"))])
    def test_unpriced_supplier_values_return_none(
        self, pricing: SupplierRetailPricing, cost, suggested
    ) -> None:
        assert pricing.retail_price_cad(cost, suggested) is None


class TestConstruction:
    def test_usd_to_cad_rounds_to_cents(self, pricing: SupplierRetailPricing) -> None:
        assert pricing.usd_to_cad(Decimal("3.333")) == Decimal("4.67")

    @pytest.mark.parametrize("rate, markup", [(Decimal("0"), Decimal("2")), (Decimal("1.3"), Decimal("0.9"))])
    def test_rejects_invalid_configuration(self, rate, markup) -> None:
        with pytest.raises(ValueError):
            SupplierRetailPricing(usd_to_cad_rate=rate, markup_multiplier=markup)
