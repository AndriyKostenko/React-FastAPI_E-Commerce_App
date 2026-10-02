"""
The payment consumer's subscribers, driven through FastStream's in-memory
broker: a JSON message published the way order-service publishes it must
reach the business logic as a dict.

The subscribers declared their body as ``str`` and parsed it themselves, but
FastStream decodes JSON before validation, so every capture, release and
order-cancelled message failed validation and was dead-lettered. Only the
PaymentEventConsumer is replaced; routing and decoding are the real ones.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from faststream.rabbit import TestRabbitBroker

from events_consumer import app as consumer_app
from shared.enums.event_enums import OrderEvents, PaymentCommands


@pytest.fixture
def business_logic() -> Iterator[MagicMock]:
    consumer = MagicMock()
    consumer.handle_payment_event = AsyncMock()
    with patch.object(consumer_app, "get_payment_event_consumer", return_value=consumer):
        yield consumer


@pytest.mark.parametrize(
    "routing_key",
    [PaymentCommands.CAPTURE_REQUESTED, PaymentCommands.RELEASE_REQUESTED, OrderEvents.ORDER_CANCELLED],
)
async def test_a_published_json_message_reaches_the_handler_as_a_dict(
    business_logic: MagicMock, routing_key: str
) -> None:
    payload = {"event_id": str(uuid4()), "event_type": routing_key, "order_id": str(uuid4())}

    async with TestRabbitBroker(consumer_app.rabbitmq_broker) as broker:
        await broker.publish(payload, exchange=consumer_app.order_exchange, routing_key=routing_key)

    business_logic.handle_payment_event.assert_awaited_once_with(payload)
