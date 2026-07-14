"""Unit tests for the order_service event consumer."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from events_consumer.order_event_consumer import OrderEventConsumer
from shared.enums.event_enums import OrderEvents
from shared.enums.status_enums import OrderStatus


TEST_ORDER_ID = uuid4()
TEST_USER_ID = uuid4()
TEST_CJ_ORDER_NUMBER = "CJORDER123"


def _make_order_schema(amount: float = 99.99):
    from datetime import datetime, timezone
    from shared.schemas.order_schemas import OrderSchema
    return OrderSchema(
        id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="test@example.com",
        amount=amount,
        currency="USD",
        status=OrderStatus.CONFIRMED,
        delivery_status="pending",
        payment_intent_id="pi_123",
        address_id=uuid4(),
        cj_order_number=None,
        date_created=datetime.now(timezone.utc),
        date_updated=None,
    )


def _make_consumer():
    consumer = OrderEventConsumer(logger=MagicMock())
    consumer.idempotency_service = MagicMock()
    consumer.idempotency_service.try_claim_event = AsyncMock(return_value=True)
    consumer.idempotency_service.mark_event_as_processed = AsyncMock()
    consumer.idempotency_service.release_claim = AsyncMock()

    order_service = MagicMock()
    order_service.get_order_by_id = AsyncMock(return_value=_make_order_schema())
    order_service.update_order = AsyncMock(return_value=_make_order_schema())

    async def _fake_get_order_service():
        yield order_service

    consumer._get_order_service = _fake_get_order_service
    return consumer, order_service


def _make_cj_order_created_message(**overrides) -> dict:
    message = {
        "event_id": str(uuid4()),
        "timestamp": "2026-07-14T00:00:00+00:00",
        "service": "supplier-service",
        "event_type": OrderEvents.CJ_ORDER_CREATED,
        "order_id": str(TEST_ORDER_ID),
        "user_id": str(TEST_USER_ID),
        "user_email": "test@example.com",
        "cj_order_number": TEST_CJ_ORDER_NUMBER,
    }
    message.update(overrides)
    return message


class TestHandleCJOrderCreated:
    async def test_persists_cj_order_number(self):
        consumer, order_service = _make_consumer()

        await consumer.handle_cj_order_created(_make_cj_order_created_message())

        order_service.get_order_by_id.assert_awaited_once_with(order_id=TEST_ORDER_ID)
        order_service.update_order.assert_awaited_once()
        update_call = order_service.update_order.call_args
        assert update_call.kwargs["order_data"].cj_order_number == TEST_CJ_ORDER_NUMBER
        consumer.idempotency_service.mark_event_as_processed.assert_awaited_once()

    async def test_duplicate_event_is_skipped(self):
        consumer, order_service = _make_consumer()
        consumer.idempotency_service.try_claim_event = AsyncMock(return_value=False)

        await consumer.handle_cj_order_created(_make_cj_order_created_message())

        order_service.get_order_by_id.assert_not_awaited()
        order_service.update_order.assert_not_awaited()
