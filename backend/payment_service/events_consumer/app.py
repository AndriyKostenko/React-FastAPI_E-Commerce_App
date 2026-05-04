from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue
from orjson import loads

from shared.shared_instances import rabbitmq_broker, order_exchange
from events_consumer.payment_event_consumer import payment_event_consumer
from shared.enums.event_enums import OrderEvents


app = FastStream(rabbitmq_broker)

# The payment service listens for order.cancelled events so it can issue
# Stripe refunds when an order is cancelled after a successful payment.
payment_order_events_queue = RabbitQueue(
    "payment.order.events.queue",
    durable=True,
    routing_key=OrderEvents.ORDER_CANCELLED,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "payment.order.events.dlq",
    },
)


@rabbitmq_broker.subscriber(queue=payment_order_events_queue, exchange=order_exchange)
async def handle_payment_events(body: str) -> None:
    """
    FastStream subscriber for order events that require payment action.
    Delegates to PaymentEventConsumer for business logic.
    """
    message: dict[str, Any] = loads(body)
    await payment_event_consumer.handle_payment_event(message)
