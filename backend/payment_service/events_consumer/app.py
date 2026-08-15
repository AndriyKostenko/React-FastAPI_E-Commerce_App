from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue
from orjson import loads

from config import logger, settings
from events_consumer.payment_event_consumer import PaymentEventConsumer
from messaging import create_rabbitmq_broker, order_exchange
from resources import PaymentConsumerResources, create_consumer_resources
from shared.enums.event_enums import OrderEvents


rabbitmq_broker = create_rabbitmq_broker(settings)
app = FastStream(rabbitmq_broker)
_resources: PaymentConsumerResources | None = None
_consumer: PaymentEventConsumer | None = None


def get_payment_event_consumer() -> PaymentEventConsumer:
    if _consumer is None:
        raise RuntimeError("Payment consumer resources are not initialized")
    return _consumer


@app.on_startup
async def startup() -> None:
    global _consumer, _resources
    resources = create_consumer_resources()
    try:
        await resources.start()
    except Exception:
        await resources.close()
        raise
    _resources = resources
    _consumer = PaymentEventConsumer(
        logger=resources.logger,
        settings=resources.settings,
        database=resources.database,
        idempotency_service=resources.idempotency,
    )
    logger.info("Payment event consumer resources started")


@app.on_shutdown
async def shutdown() -> None:
    global _consumer, _resources
    resources, _resources = _resources, None
    _consumer = None
    if resources is not None:
        await resources.close()
    logger.info("Payment event consumer resources closed")

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
    await get_payment_event_consumer().handle_payment_event(message)
