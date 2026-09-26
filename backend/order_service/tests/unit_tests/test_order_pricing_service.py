from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from schemas.order_schemas import AddressType, CreateOrder, OrderProductItem
from service_layer.order_pricing_service import OrderPricingService, OrderQuoteError
from shared.contracts.tax import TaxCalculationResult
from shared.contracts.artwork import GeneratedArtworkAsset, sign_artwork_asset
from shared.contracts.order import CustomTshirtSpecification


_SECRET = "test-artwork-signing-secret"


def _settings(**overrides):
    values = dict(
        STRIPE_TAX_ENABLED=False,
        CUSTOM_TSHIRT_BASE_PRICE=Decimal("19.00"),
        ARTWORK_SIGNING_KEY=_SECRET,
        PRINT_IMAGE_MIN_EFFECTIVE_DPI=150,
        DOMESTIC_FLAT_SHIPPING_CAD=Decimal("9.99"),
        CJ_USD_TO_CAD_RATE=Decimal("1.40"),
        CJ_FX_SOURCE="fixed",
        CJ_PRICE_MARKUP_MULTIPLIER=Decimal("2.00"),
        CJ_FREIGHT_PRICE_BUFFER=Decimal("0.10"),
    )
    return SimpleNamespace(**{**values, **overrides})


def _freight_client():
    return SimpleNamespace(
        quote=AsyncMock(
            return_value=[
                {"logistic_name": "CJPacket Ordinary", "price": "5.00", "delivery_time": "10-20"},
                {"logistic_name": "CJPacket Express", "price": "12.00", "delivery_time": "5-8"},
            ]
        )
    )


def _asset(width: int = 4096, height: int = 4096) -> GeneratedArtworkAsset:
    unsigned = GeneratedArtworkAsset(
        key="generated-designs/2026/08/" + "a" * 32 + ".png",
        width_px=width,
        height_px=height,
        embedded_dpi=300,
        sha256="b" * 64,
        token="0" * 43,
    )
    return unsigned.model_copy(update={"token": sign_artwork_asset(unsigned, _SECRET)})


def _custom_spec(asset: GeneratedArtworkAsset | None = None):
    return CustomTshirtSpecification(
        design_asset=asset or _asset(),
        prompt="A mountain at sunrise",
        style="Watercolor",
        size="M",
        garment_color="black",
        placement="Full Back",
        gender="X",
    )


def _order(products, shipping_logistic_name=None, **address_overrides):
    address = {
        "street": "1 Main St",
        "city": "Calgary",
        "province": "AB",
        "postal_code": "T1T 1T1",
        "country": "Canada",
        "country_code": "CA",
        "name": "Buyer",
        "phone": "+14035550100",
        **address_overrides,
    }
    return CreateOrder(
        user_id=uuid4(),
        user_email="buyer@example.com",
        products=products,
        address=AddressType(**address),
        shipping_logistic_name=shipping_logistic_name,
    )


def _cj_catalog_client(product_id, unit_price="31.25"):
    return SimpleNamespace(
        quote=AsyncMock(
            return_value={
                "items": [
                    {
                        "product_id": str(product_id),
                        "variant_id": str(uuid4()),
                        "product_name": "CJ Shirt",
                        "quantity": 1,
                        "unit_price": unit_price,
                        "fulfillment_type": "cj",
                        "supplier_id": "cjdropshipping",
                    }
                ]
            }
        )
    )


async def test_custom_quote_ignores_client_price_and_uses_server_rules():
    catalog_client = SimpleNamespace(quote=AsyncMock())
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=catalog_client,
    )

    quote = await service.build_quote(
        _order(
            [
                OrderProductItem(
                    id=uuid4(),
                    price=Decimal("0.01"),
                    quantity=2,
                    fulfillment_type="custom",
                    customization=_custom_spec(),
                )
            ]
        )
    )

    assert quote.items[0].unit_price == Decimal("24.28")
    assert quote.subtotal_amount == Decimal("48.56")
    # Custom prints ship from here: one flat domestic charge, no CJ freight.
    assert quote.shipping_amount == Decimal("9.99")
    assert quote.total_amount == Decimal("58.55")
    assert quote.amount_cents == 5855
    assert quote.shipping_options == []
    assert quote.items[0].customization is not None
    assert quote.items[0].customization.print_width_in == 15
    assert quote.items[0].customization.print_height_in == 18
    assert quote.items[0].customization.effective_dpi == 227.56
    catalog_client.quote.assert_not_awaited()


async def test_custom_quote_rejects_tampered_asset_metadata():
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=SimpleNamespace(quote=AsyncMock()),
    )
    tampered = _asset().model_copy(update={"width_px": 5000})

    with pytest.raises(OrderQuoteError, match="metadata is invalid"):
        await service.build_quote(
            _order(
                [
                    OrderProductItem(
                        quantity=1,
                        fulfillment_type="custom",
                        customization=_custom_spec(tampered),
                    )
                ]
            )
        )


async def test_custom_quote_rejects_resolution_too_low_for_placement():
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=SimpleNamespace(quote=AsyncMock()),
    )

    with pytest.raises(OrderQuoteError, match="resolution is too low"):
        await service.build_quote(
            _order(
                [
                    OrderProductItem(
                        quantity=1,
                        fulfillment_type="custom",
                        customization=_custom_spec(_asset(1024, 1024)),
                    )
                ]
            )
        )


async def test_mixed_quote_preserves_line_order_and_canonical_catalog_values():
    catalog_id = uuid4()
    catalog_client = SimpleNamespace(
        quote=AsyncMock(
            return_value={
                "items": [
                    {
                        "product_id": str(catalog_id),
                        "variant_id": str(uuid4()),
                        "product_name": "CJ Shirt",
                        "quantity": 1,
                        "unit_price": "31.25",
                        "fulfillment_type": "cj",
                        "supplier_id": "cjdropshipping",
                    }
                ]
            }
        )
    )
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=catalog_client,
        freight_client=_freight_client(),
    )

    quote = await service.build_quote(
        _order(
            [
                OrderProductItem(
                    quantity=1,
                    fulfillment_type="custom",
                    customization=_custom_spec(),
                ),
                OrderProductItem(id=catalog_id, quantity=1),
            ]
        )
    )

    assert [line.fulfillment_type for line in quote.items] == ["custom", "cj"]
    assert quote.subtotal_amount == Decimal("55.53")
    # Flat 9.99 for the custom print plus the cheapest CJ option:
    # 5.00 USD padded 10% = 5.50 USD x 1.40 = 7.70 CAD.
    assert quote.shipping_amount == Decimal("17.69")
    assert quote.total_amount == Decimal("73.22")
    assert quote.shipping_logistic_name == "CJPacket Ordinary"


async def test_cj_only_quote_charges_selected_freight_without_domestic_rate():
    product_id = uuid4()
    freight_client = _freight_client()
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=_cj_catalog_client(product_id),
        freight_client=freight_client,
    )

    quote = await service.build_quote(
        _order(
            [OrderProductItem(id=product_id, variant_id=uuid4(), quantity=1)],
            shipping_logistic_name="CJPacket Express",
        )
    )

    # 12.00 USD padded 10% = 13.20 USD x 1.40 = 18.48 CAD.
    assert quote.shipping_amount == Decimal("18.48")
    assert quote.total_amount == Decimal("49.73")
    assert [o.logistic_name for o in quote.shipping_options] == [
        "CJPacket Ordinary",
        "CJPacket Express",
    ]
    assert quote.shipping_options[1].cost_usd == Decimal("12.00")
    # The customer never sees CJ's cost in a serialized quote.
    assert "cost_usd" not in quote.shipping_options[1].model_dump()
    freight_client.quote.assert_awaited_once()
    assert freight_client.quote.await_args.kwargs["country_code"] == "CA"


async def test_quote_refuses_a_shipping_option_cj_no_longer_offers():
    product_id = uuid4()
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=_cj_catalog_client(product_id),
        freight_client=_freight_client(),
    )

    with pytest.raises(OrderQuoteError, match="no longer available"):
        await service.build_quote(
            _order(
                [OrderProductItem(id=product_id, variant_id=uuid4(), quantity=1)],
                shipping_logistic_name="Teleport",
            )
        )


async def test_cj_quote_requires_fulfillment_address_before_calling_cj():
    product_id = uuid4()
    freight_client = _freight_client()
    service = OrderPricingService(
        settings=_settings(),
        catalog_client=_cj_catalog_client(product_id),
        freight_client=freight_client,
    )

    with pytest.raises(OrderQuoteError, match="phone"):
        await service.build_quote(
            _order(
                [OrderProductItem(id=product_id, variant_id=uuid4(), quantity=1)],
                phone=None,
            )
        )
    freight_client.quote.assert_not_awaited()


# ---------------------------------------------------------------- sales tax


def _custom_line(quantity: int = 2) -> OrderProductItem:
    return OrderProductItem(
        id=uuid4(), quantity=quantity, fulfillment_type="custom", customization=_custom_spec()
    )


def _tax_client(tax_cents: int, total_cents: int, calculation_id: str = "taxcalc_123"):
    return SimpleNamespace(
        calculate=AsyncMock(
            return_value=TaxCalculationResult(
                calculation_id=calculation_id, tax_cents=tax_cents, total_cents=total_cents
            )
        )
    )


async def test_tax_is_zero_and_never_calculated_while_disabled():
    tax_client = _tax_client(293, 6148)
    service = OrderPricingService(
        settings=_settings(STRIPE_TAX_ENABLED=False),
        catalog_client=SimpleNamespace(quote=AsyncMock()),
        tax_client=tax_client,
    )

    quote = await service.build_quote(_order([_custom_line()]))

    assert quote.tax_amount == Decimal("0.00")
    assert quote.tax_calculation_id is None
    assert quote.total_amount == Decimal("58.55")
    tax_client.calculate.assert_not_awaited()


async def test_enabled_tax_is_added_to_the_total_and_its_calculation_kept():
    tax_client = _tax_client(293, 6148)
    service = OrderPricingService(
        settings=_settings(STRIPE_TAX_ENABLED=True),
        catalog_client=SimpleNamespace(quote=AsyncMock()),
        tax_client=tax_client,
    )

    quote = await service.build_quote(_order([_custom_line()]))

    assert quote.tax_amount == Decimal("2.93")
    assert quote.total_amount == Decimal("61.48")  # 48.56 + 9.99 shipping + 2.93 tax
    assert quote.amount_cents == 6148
    assert quote.tax_calculation_id == "taxcalc_123"

    request = tax_client.calculate.await_args.args[0]
    # Lines go in tax-exclusive, in cents, with shipping on its own.
    assert [(line.amount_cents, line.quantity) for line in request.lines] == [(4856, 2)]
    assert request.shipping_cents == 999
    assert request.currency == "CAD"
    assert request.address.country == "CA"
    assert request.address.state == "AB"
    assert request.address.postal_code == "T1T 1T1"


async def test_enabled_tax_needs_a_country_code():
    service = OrderPricingService(
        settings=_settings(STRIPE_TAX_ENABLED=True),
        catalog_client=SimpleNamespace(quote=AsyncMock()),
        tax_client=_tax_client(0, 0),
    )

    with pytest.raises(OrderQuoteError, match="country_code"):
        await service.build_quote(_order([_custom_line()], country_code=None))
