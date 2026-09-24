from typing import Any

from faststream import FastStream
from faststream.rabbit.annotations import RabbitMessage

from config import logger, settings
from events_consumer.order_event_consumer import OrderEventConsumer
from messaging import (
    create_rabbitmq_broker,
    inventory_exchange,
    order_exchange,
    payment_exchange,
    shipping_exchange,
)
from resources import OrderConsumerResources, create_consumer_resources
from shared.enums.event_enums import OrderSagaResponseQueue
from shared.messaging import ConsumerTopology


# Create the FastStream app
rabbitmq_broker = create_rabbitmq_broker(settings)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)
_resources: OrderConsumerResources | None = None
_consumer: OrderEventConsumer | None = None


def get_order_event_consumer() -> OrderEventConsumer:
    if _consumer is None:
        raise RuntimeError("Order consumer resources are not initialized")
    return _consumer


@app.on_startup
async def startup() -> None:
    global _consumer, _resources
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
    resources = create_consumer_resources(rabbitmq_broker)
    try:
        await resources.start()
    except Exception:
        await resources.close()
        raise
    _resources = resources
    _consumer = OrderEventConsumer(
        logger=resources.logger,
        database=resources.database,
        idempotency_service=resources.idempotency,
        event_publisher=resources.publisher,
    )
    logger.info("Order event consumer resources started")


@app.on_shutdown
async def shutdown() -> None:
    global _consumer, _resources
    resources, _resources = _resources, None
    _consumer = None
    if resources is not None:
        await resources.close()
    logger.info("Order event consumer resources closed")


# inventory.reserve.* binds to inventory.reserve.succeeded and inventory.reserve.failed
order_saga_response_queue = topology.queue(
    name=OrderSagaResponseQueue.ORDER_SAGA_RESPONSE_QUEUE,
    routing_key="inventory.reserve.*", # Listen to both success and failure of inventory reservation
    dead_letter_key=OrderSagaResponseQueue.ORDER_SAGA_RESPONSE_DEAD_LETTER_QUEUE,
)

# Listens for payment.failed and payment.cancelled so the order can be cancelled
# when Stripe reports a failure or cancels the PaymentIntent
order_payment_events_queue = topology.queue(
    name="order.payment.events.queue",
    routing_key="payment.*",  # binds payment.failed and payment.cancelled
    dead_letter_key="order.payment.events.dlq",
)


# Register the subscriber function (FastStream requires this at module level)
@rabbitmq_broker.subscriber(queue=order_saga_response_queue.queue, exchange=inventory_exchange)
async def handle_order_saga_responses(body: dict[str, Any], message: RabbitMessage) -> None:
    """
    FastStream subscriber function that delegates to the OrderEventConsumer class.
    This pattern gives us:
    - Class-based organization for business logic
    - Proper FastStream integration with decorators
    - Clean separation of concerns
    """
    await topology.dispatch(
        order_saga_response_queue,
        message,
        lambda: get_order_event_consumer().handle_order_saga_response(body),
    )


order_shipping_events_queue = topology.queue(
    name="order.shipping.events.queue",
    routing_key="shipping.*",
    dead_letter_key="order.shipping.events.dlq",
)


@rabbitmq_broker.subscriber(queue=order_payment_events_queue.queue, exchange=payment_exchange)
async def handle_order_payment_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """
    FastStream subscriber for payment events that affect order state.
    Routes payment.failed to handle_payment_failed so the order is cancelled
    and any reserved inventory is released.
    """
    await topology.dispatch(
        order_payment_events_queue,
        message,
        lambda: get_order_event_consumer().handle_payment_event(body),
    )


@rabbitmq_broker.subscriber(queue=order_shipping_events_queue.queue, exchange=shipping_exchange)
async def handle_order_shipping_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """FastStream subscriber for shipping events that affect order delivery status."""
    await topology.dispatch(
        order_shipping_events_queue,
        message,
        lambda: get_order_event_consumer().handle_shipping_event(body),
    )


# "cj.order.*" covers created / shipped / delivered / failed — the whole CJ
# fulfillment lifecycle lands on this one queue.
cj_order_events_queue = topology.queue(
    name="order.cj.order.events.queue",
    routing_key="cj.order.*",
    dead_letter_key="order.cj.order.created.dlq",
)


@rabbitmq_broker.subscriber(queue=cj_order_events_queue.queue, exchange=order_exchange)
async def handle_cj_order_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """Track CJ fulfillment progress or compensate a definitive CJ failure."""
    await topology.dispatch(
        cj_order_events_queue,
        message,
        lambda: get_order_event_consumer().handle_cj_order_event(body),
    )
