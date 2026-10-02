"""The createOrderV2 body: shipped from CJ's China warehouse, to Canada only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from exceptions.cj_order_exceptions import CJAddressValidationError
from service_layer.cj_address_validator import CJShippingAddressValidator
from service_layer.cj_inventory_verifier import StockVerificationResult
from service_layer.cj_order_payload_builder import CJOrderPayloadBuilder
from shared.contracts.events import OrderConfirmedEvent
from shared.contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem
from shared.settings import get_settings


def _event(**address: str) -> OrderConfirmedEvent:
    fields = {
        "street": "12 Main Street", "city": "Calgary", "province": "AB", "postal_code": "T2T 2T2",
        "country": "Canada", "country_code": "CA", "name": "Buyer", "phone": "+1 403 555 0100",
    }
    return OrderConfirmedEvent(
        order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
        items=[ConfirmedOrderItem(product_id=uuid4(), variant_id=uuid4(), quantity=2, price=19.99, fulfillment_type="cj")],
        address=ConfirmedOrderAddress(**{**fields, **address}),
        shipping_logistic_name="CJPacket Ordinary",
    )


def _builder(sandbox: bool = False) -> tuple[CJOrderPayloadBuilder, SimpleNamespace, SimpleNamespace]:
    settings = get_settings().model_copy(update={"CJ_DROPSHIPPING_SANDBOX": sandbox})
    products = SimpleNamespace(resolve_cj_ids=AsyncMock(return_value=("PID-1", "VID-1")))
    verifier = SimpleNamespace(verify_variant_stock=AsyncMock(return_value=StockVerificationResult(
        requested=2, available=10, sufficient=True, buffered_available=10, warehouses_checked=1,
    )))
    builder = CJOrderPayloadBuilder(
        settings=settings,
        product_service_client=products,
        inventory_verifier=verifier,
        address_validator=CJShippingAddressValidator(settings),
    )
    return builder, products, verifier


async def test_the_order_ships_from_the_us_warehouse_to_canada() -> None:
    builder, _, _ = _builder()

    body = await builder.build(_event())

    assert body["fromCountryCode"] == "CN"
    assert body["shippingCountryCode"] == "CA"
    assert body["products"] == [{"vid": "VID-1", "quantity": 2}]


@pytest.mark.parametrize(
    ("country_code", "postal_code"), [("US", "10001"), ("GB", "SW1A 1AA")]
)
async def test_an_order_to_another_country_never_reaches_cj(country_code: str, postal_code: str) -> None:
    builder, products, verifier = _builder()

    with pytest.raises(CJAddressValidationError, match="Canada only"):
        await builder.build(_event(country="Elsewhere", country_code=country_code, postal_code=postal_code))

    products.resolve_cj_ids.assert_not_awaited()
    verifier.verify_variant_stock.assert_not_awaited()


async def test_a_real_order_carries_no_sandbox_flag() -> None:
    builder, _, _ = _builder(sandbox=False)

    assert "isSandbox" not in await builder.build(_event())


async def test_with_the_sandbox_on_the_order_is_created_as_a_sandbox_order() -> None:
    builder, _, _ = _builder(sandbox=True)

    body = await builder.build(_event())

    assert body["isSandbox"] == 1
    # Everything else is the real order: same origin, destination and lines.
    assert (body["fromCountryCode"], body["shippingCountryCode"]) == ("CN", "CA")
