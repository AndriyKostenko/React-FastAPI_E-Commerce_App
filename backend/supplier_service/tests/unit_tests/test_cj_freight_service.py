"""Unit tests for CJFreightQuoteService."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from exceptions.cj_order_exceptions import CJFreightQuoteError
from schemas.dropshipping_schemas import CJFreightQuoteRequest
from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_freight_service import CJFreightQuoteService, FreightQuoteCache
from service_layer.product_service_client import ProductNotFoundError
from shared.settings import get_settings


TEST_PRODUCT_ID = uuid4()
TEST_VARIANT_ID = uuid4()
TEST_VID = "CJVID456"

CJ_RESPONSE = {
    "result": True,
    "code": 200,
    "data": [
        {"logisticName": "CJPacket Sensitive", "logisticPrice": "9.10", "logisticAging": "12-20"},
        {"logisticName": "CJPacket Ordinary", "logisticPrice": 5.32, "logisticAging": "7-12", "logisticWeight": 120},
    ],
}


def _make_service(
    *,
    cj_response: dict | Exception = CJ_RESPONSE,
    resolve_cj_ids: tuple[str, str] | Exception = ("CJPID123", TEST_VID),
    cache_ttl_seconds: float = 300.0,
) -> CJFreightQuoteService:
    api_client = MagicMock()
    if isinstance(cj_response, Exception):
        api_client.calculate_freight = AsyncMock(side_effect=cj_response)
    else:
        api_client.calculate_freight = AsyncMock(return_value=cj_response)

    product_client = MagicMock()
    if isinstance(resolve_cj_ids, Exception):
        product_client.resolve_cj_ids = AsyncMock(side_effect=resolve_cj_ids)
    else:
        product_client.resolve_cj_ids = AsyncMock(return_value=resolve_cj_ids)

    return CJFreightQuoteService(
        api_client=api_client,
        product_service_client=product_client,
        settings=get_settings(),
        logger=MagicMock(),
        cache=FreightQuoteCache(ttl_seconds=cache_ttl_seconds, max_entries=8),
    )


def _request(**overrides) -> CJFreightQuoteRequest:
    fields = {
        "country_code": "us",
        "postal_code": "10001",
        "items": [
            {
                "product_id": TEST_PRODUCT_ID,
                "variant_id": TEST_VARIANT_ID,
                "quantity": 2,
            }
        ],
    }
    fields.update(overrides)
    return CJFreightQuoteRequest(**fields)


class TestQuote:
    async def test_returns_options_cheapest_first(self) -> None:
        service = _make_service()

        response = await service.quote(_request())

        assert response.country_code == "US"
        assert [option.logistic_name for option in response.options] == [
            "CJPacket Ordinary",
            "CJPacket Sensitive",
        ]
        assert response.options[0].price == Decimal("5.32")
        assert response.options[0].delivery_time == "7-12"
        assert response.options[0].weight_grams == Decimal("120")

    async def test_sends_resolved_vids_and_destination_to_cj(self) -> None:
        service = _make_service()

        await service.quote(_request())

        payload = service.api_client.calculate_freight.await_args.args[0]
        assert payload["endCountryCode"] == "US"
        assert payload["zip"] == "10001"
        assert payload["products"] == [{"vid": TEST_VID, "quantity": 2}]
        assert payload["startCountryCode"]

    async def test_collapses_duplicate_variants_into_one_line(self) -> None:
        service = _make_service()
        item = {
            "product_id": TEST_PRODUCT_ID,
            "variant_id": TEST_VARIANT_ID,
            "quantity": 3,
        }

        await service.quote(_request(items=[item, item]))

        payload = service.api_client.calculate_freight.await_args.args[0]
        assert payload["products"] == [{"vid": TEST_VID, "quantity": 6}]

    async def test_omits_zip_when_not_supplied(self) -> None:
        service = _make_service()

        await service.quote(_request(postal_code=None))

        assert "zip" not in service.api_client.calculate_freight.await_args.args[0]

    async def test_repeated_quote_is_served_from_cache(self) -> None:
        service = _make_service()

        await service.quote(_request())
        await service.quote(_request())

        service.api_client.calculate_freight.assert_awaited_once()

    async def test_disabled_cache_always_calls_cj(self) -> None:
        service = _make_service(cache_ttl_seconds=0)

        await service.quote(_request())
        await service.quote(_request())

        assert service.api_client.calculate_freight.await_count == 2

    async def test_different_destination_is_not_a_cache_hit(self) -> None:
        service = _make_service()

        await service.quote(_request())
        await service.quote(_request(country_code="CA", postal_code="M5V2T6"))

        assert service.api_client.calculate_freight.await_count == 2


class TestQuoteFailures:
    async def test_no_shippable_option_is_rejected(self) -> None:
        service = _make_service(cj_response={"result": True, "code": 200, "data": []})

        with pytest.raises(CJFreightQuoteError, match="no shipping option"):
            await service.quote(_request())

    async def test_unpriced_options_are_skipped(self) -> None:
        service = _make_service(
            cj_response={
                "result": True,
                "data": [
                    {"logisticName": "Broken", "logisticPrice": None},
                    {"logisticName": "Usable", "logisticPrice": "3.00"},
                ],
            }
        )

        response = await service.quote(_request())

        assert [option.logistic_name for option in response.options] == ["Usable"]

    async def test_cj_error_becomes_a_quote_error(self) -> None:
        service = _make_service(cj_response=CJDropshippingAPIError("CJ is down"))

        with pytest.raises(CJFreightQuoteError, match="could not price shipping"):
            await service.quote(_request())

    async def test_unmappable_product_becomes_a_quote_error(self) -> None:
        service = _make_service(resolve_cj_ids=ProductNotFoundError("missing"))

        with pytest.raises(CJFreightQuoteError, match="not found"):
            await service.quote(_request())

        service.api_client.calculate_freight.assert_not_awaited()

    async def test_malformed_cj_payload_is_rejected(self) -> None:
        service = _make_service(cj_response={"result": True, "data": {"oops": 1}})

        with pytest.raises(CJFreightQuoteError, match="not a list"):
            await service.quote(_request())


class TestFreightQuoteCache:
    def test_evicts_when_over_capacity(self) -> None:
        cache = FreightQuoteCache(ttl_seconds=60, max_entries=2)
        for index in range(3):
            cache.put((f"C{index}", "", ()), [])

        assert cache.get(("C0", "", ())) is None
        assert cache.get(("C2", "", ())) == []
