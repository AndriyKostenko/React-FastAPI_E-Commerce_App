from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from events_consumer.shipping_event_consumer import ShippingEventConsumer
from shared.enums.event_enums import OrderEvents


@pytest.mark.parametrize("fulfillment_type", ["cj", "custom"])
@pytest.mark.asyncio
async def test_confirmed_external_or_custom_order_does_not_create_local_shipment(
    fulfillment_type: str,
) -> None:
    idempotency = MagicMock()
    idempotency.try_claim_event = AsyncMock(return_value=True)
    idempotency.mark_event_as_processed = AsyncMock()
    idempotency.release_claim = AsyncMock()
    consumer = ShippingEventConsumer(
        logger=MagicMock(),
        database=MagicMock(),
        idempotency=idempotency,
        event_publisher=MagicMock(),
    )
    consumer._get_shipment_service = MagicMock()

    event_id = uuid4()
    order_id = uuid4()
    await consumer.handle_order_confirmed(
        {
            "event_id": str(event_id),
            "event_type": OrderEvents.ORDER_CONFIRMED,
            "order_id": str(order_id),
            "user_id": str(uuid4()),
            "user_email": "buyer@example.com",
            "items": [
                {
                    "product_id": str(uuid4()),
                    "quantity": 1,
                    "price": 25.0,
                    "fulfillment_type": fulfillment_type,
                }
            ],
        }
    )

    consumer._get_shipment_service.assert_not_called()
    idempotency.mark_event_as_processed.assert_awaited_once_with(
        event_id=event_id,
        event_type=OrderEvents.ORDER_CONFIRMED,
        order_id=order_id,
        result="external_or_production_fulfillment",
    )
