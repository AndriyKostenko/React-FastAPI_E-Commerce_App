from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, order_exchange
from events_consumer.shipping_event_consumer import shipping_event_consumer
from shared.enums.event_enums import ShippingEventsQueue, OrderEvents


app = FastStream(rabbitmq_broker)


shipping_order_events_queue = RabbitQueue(
    name=ShippingEventsQueue.SHIPPING_EVENTS_QUEUE,
    durable=True,
    routing_key="order.*",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": ShippingEventsQueue.SHIPPING_EVENTS_DEAD_LETTER_QUEUE,
    },
)


@rabbitmq_broker.subscriber(queue=shipping_order_events_queue, exchange=order_exchange)
async def handle_shipping_order_events(body: dict[str, Any]) -> None:
    """Consume order lifecycle events relevant to shipping."""
    await shipping_event_consumer.handle_order_event(body)
