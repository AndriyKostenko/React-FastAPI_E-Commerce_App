from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, order_exchange
from events_consumer.cart_event_consumer import cart_event_consumer
from shared.enums.event_enums import CartEventsQueue, OrderEvents


# Create the FastStream app
app = FastStream(rabbitmq_broker)


# Queue that receives order lifecycle events relevant to the cart.
# Binds to order.created and order.confirmed so the cart can be cleared
# when a purchase is finalized.
cart_order_events_queue = RabbitQueue(
    name=CartEventsQueue.CART_ORDER_EVENTS_QUEUE,
    durable=True,
    routing_key="order.*",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": CartEventsQueue.CART_ORDER_EVENTS_DEAD_LETTER_QUEUE,
    },
)


@rabbitmq_broker.subscriber(queue=cart_order_events_queue, exchange=order_exchange)
async def handle_cart_order_events(body: dict[str, Any]) -> None:
    """
    FastStream subscriber that delegates order events to CartEventConsumer.

    The consumer listens to order.created (and order.confirmed as a safety-net)
    and clears the corresponding user's shopping cart.
    """
    await cart_event_consumer.handle_order_event(body)
