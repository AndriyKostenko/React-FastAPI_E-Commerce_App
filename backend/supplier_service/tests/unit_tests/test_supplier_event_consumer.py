"""Unit tests for supplier_service event consumer."""
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from event_consumer.supplier_event_consumer import SupplierEventConsumer
from exceptions.cj_order_exceptions import CJOrderCreationError
from service_layer.cj_api_client import CJDropshippingAPIError
from shared.enums.event_enums import InventoryEvents, OrderEvents


TEST_ORDER_ID = uuid4()
TEST_USER_ID = uuid4()
TEST_PRODUCT_ID = uuid4()
TEST_VARIANT_ID = uuid4()
TEST_PID = "CJPID123"
TEST_VID = "CJVID456"
TEST_CJ_ORDER_NUMBER = "CJORDER789"


def _make_consumer(
    *,
    claim_event: bool = True,
    resolve_cj_ids: tuple[str, str] | Exception | None = None,
    create_order_response: dict | Exception | None = None,
):
    logger = MagicMock()
    idempotency = MagicMock()
    idempotency.try_claim_event = AsyncMock(return_value=claim_event)
    idempotency.mark_event_as_processed = AsyncMock()
    idempotency.release_claim = AsyncMock()

    cj_client = MagicMock()
    if isinstance(create_order_response, Exception):
        cj_client.create_order_v2 = AsyncMock(side_effect=create_order_response)
    else:
        cj_client.create_order_v2 = AsyncMock(return_value=create_order_response)

    product_client = MagicMock()
    if isinstance(resolve_cj_ids, Exception):
        product_client.resolve_cj_ids = AsyncMock(side_effect=resolve_cj_ids)
    else:
        product_client.resolve_cj_ids = AsyncMock(return_value=resolve_cj_ids)

    publisher = MagicMock()
    publisher.publish_cj_order_created = AsyncMock()
    publisher.publish_order_cancelled = AsyncMock()
    publisher.publish_inventory_release_requested = AsyncMock()

    consumer = SupplierEventConsumer(
        logger=logger,
        idempotency_service=idempotency,
        cj_api_client=cj_client,
        product_service_client=product_client,
        publisher=publisher,
    )
    return consumer


def _make_order_confirmed_message(**overrides) -> dict:
    message = {
        "event_id": str(uuid4()),
        "timestamp": "2026-07-14T00:00:00+00:00",
        "service": "order-service",
        "event_type": OrderEvents.ORDER_CONFIRMED,
        "order_id": str(TEST_ORDER_ID),
        "user_id": str(TEST_USER_ID),
        "user_email": "test@example.com",
        "items": [
            {
                "product_id": str(TEST_PRODUCT_ID),
                "variant_id": str(TEST_VARIANT_ID),
                "quantity": 2,
                "price": 49.99,
            }
        ],
        "address": {
            "street": "123 Test St",
            "city": "Testville",
            "province": "TS",
            "postal_code": "T1T 1T1",
            "country": "Canada",
            "country_code": "CA",
            "name": "Test User",
            "phone": "+1234567890",
        },
    }
    message.update(overrides)
    return message


class TestHandleOrderConfirmed:
    async def test_creates_cj_order_and_publishes_event(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={
                "result": True,
                "code": 200,
                "data": {"orderId": TEST_CJ_ORDER_NUMBER},
            },
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.product_service_client.resolve_cj_ids.assert_awaited_once_with(
            product_id=TEST_PRODUCT_ID,
            variant_id=TEST_VARIANT_ID,
        )
        consumer.cj_api_client.create_order_v2.assert_awaited_once()
        consumer.publisher.publish_cj_order_created.assert_awaited_once()
        consumer.publisher.publish_order_cancelled.assert_not_awaited()
        consumer.publisher.publish_inventory_release_requested.assert_not_awaited()
        call_kwargs = consumer.publisher.publish_cj_order_created.call_args.kwargs["event_data"]
        assert call_kwargs["cj_order_number"] == TEST_CJ_ORDER_NUMBER

    async def test_duplicate_event_is_skipped(self):
        consumer = _make_consumer(claim_event=False)

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.product_service_client.resolve_cj_ids.assert_not_awaited()
        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer.publisher.publish_cj_order_created.assert_not_awaited()

    async def test_cj_api_failure_triggers_compensation(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response=CJDropshippingAPIError("CJ API error"),
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.publisher.publish_cj_order_created.assert_not_awaited()
        consumer.publisher.publish_order_cancelled.assert_awaited_once()
        consumer.publisher.publish_inventory_release_requested.assert_awaited_once()

        release_call = consumer.publisher.publish_inventory_release_requested.call_args.kwargs["event_data"]
        assert release_call["event_type"] == InventoryEvents.INVENTORY_RELEASE_REQUESTED
        assert len(release_call["items"]) == 1
        assert release_call["items"][0]["product_id"] == TEST_PRODUCT_ID

    async def test_missing_address_triggers_compensation(self):
        consumer = _make_consumer(resolve_cj_ids=(TEST_PID, TEST_VID))

        message = _make_order_confirmed_message(address=None)
        await consumer.handle_order_confirmed(message)

        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer.publisher.publish_order_cancelled.assert_awaited_once()
        consumer.publisher.publish_inventory_release_requested.assert_awaited_once()

    async def test_product_mapping_error_triggers_compensation(self):
        consumer = _make_consumer(
            resolve_cj_ids=CJDropshippingAPIError("product not found"),
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer.publisher.publish_order_cancelled.assert_awaited_once()
        consumer.publisher.publish_inventory_release_requested.assert_awaited_once()

    async def test_cj_response_missing_order_id_raises(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={"result": True, "code": 200, "data": {}},
        )

        from shared.schemas.event_schemas import OrderConfirmedEvent
        event = OrderConfirmedEvent(**_make_order_confirmed_message())
        with pytest.raises(CJOrderCreationError):
            await consumer._create_cj_order(event)
