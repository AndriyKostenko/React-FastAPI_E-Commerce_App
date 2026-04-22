from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue
from orjson import loads

from shared.shared_instances import rabbitmq_broker, payment_exchange
from events_consumer.payment_event_consumer import payment_event_consumer
from shared.enums.event_enums import PaymentEvents


app = FastStream(rabbitmq_broker)

payment_events_queue = RabbitQueue(
    "payment.events.queue", # Consumed by order service, notification service, etc.
    durable=True,
    routing_key="payment.*", # Listen to all payment events (succeeded, failed, etc.) for flexibility in handling and future expansion.
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "payment.events.dlq",
    },
)


@rabbitmq_broker.subscriber(queue=payment_events_queue, exchange=payment_exchange)
async def handle_payment_events(body: str) -> None:
    """
    FastStream subscriber for payment events.
    Delegates to PaymentEventConsumer for business logic.
    """
    message: dict[str, Any] = loads(body)
    await payment_event_consumer.handle_payment_event(message)
