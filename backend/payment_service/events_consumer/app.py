from typing import Any

from faststream import FastStream
from faststream.rabbit.annotations import RabbitMessage
from orjson import loads

from config import logger, settings
from events_consumer.payment_event_consumer import PaymentEventConsumer
from messaging import create_rabbitmq_broker, order_exchange
from resources import PaymentConsumerResources, create_consumer_resources
from shared.enums.event_enums import OrderEvents
from shared.messaging import ConsumerTopology


rabbitmq_broker = create_rabbitmq_broker(settings)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)
_resources: PaymentConsumerResources | None = None
_consumer: PaymentEventConsumer | None = None


def get_payment_event_consumer() -> PaymentEventConsumer:
    if _consumer is None:
        raise RuntimeError("Payment consumer resources are not initialized")
    return _consumer


@app.on_startup
async def startup() -> None:
    global _consumer, _resources
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
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
        stripe_client=resources.stripe_client,
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
payment_order_events_queue = topology.queue(
    name="payment.order.events.queue",
    routing_key=OrderEvents.ORDER_CANCELLED,
    dead_letter_key="payment.order.events.dlq",
)


@rabbitmq_broker.subscriber(queue=payment_order_events_queue.queue, exchange=order_exchange)
async def handle_payment_events(body: str, message: RabbitMessage) -> None:
    """
    FastStream subscriber for order events that require payment action.
    Delegates to PaymentEventConsumer for business logic.
    """
    await topology.dispatch(
        payment_order_events_queue,
        message,
        lambda: get_payment_event_consumer().handle_payment_event(loads(body)),
    )


# order_service's instructions about a held card. The "payment.*.requested"
# keys share the order exchange but match no other binding on it.
payment_commands_queue = topology.queue(
    name="payment.commands.queue",
    routing_key="payment.*.requested",
    dead_letter_key="payment.commands.dlq",
)


@rabbitmq_broker.subscriber(queue=payment_commands_queue.queue, exchange=order_exchange)
async def handle_payment_commands(body: str, message: RabbitMessage) -> None:
    """FastStream subscriber for capture and release commands from order_service."""
    await topology.dispatch(
        payment_commands_queue,
        message,
        lambda: get_payment_event_consumer().handle_payment_event(loads(body)),
    )
