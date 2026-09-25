from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage

from service_config import logger, settings
from events_consumer.cart_event_consumer import CartEventConsumer
from events_consumer.runtime import CartConsumerResources, create_cart_consumer_resources
from shared.enums.event_enums import CartEventsQueue
from shared.messaging import ConsumerTopology


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
order_exchange = RabbitExchange(
    name="order.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)
consumer_resources: CartConsumerResources | None = None
cart_event_consumer: CartEventConsumer | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, cart_event_consumer
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
    consumer_resources = create_cart_consumer_resources()
    try:
        await consumer_resources.start()
    except Exception:
        await consumer_resources.close()
        consumer_resources = None
        raise
    cart_event_consumer = CartEventConsumer(
        logger=consumer_resources.logger,
        database=consumer_resources.database,
        idempotency=consumer_resources.idempotency,
    )
    logger.info("Cart event consumer resources started.")


@app.on_shutdown
async def shutdown() -> None:
    global consumer_resources, cart_event_consumer
    try:
        if consumer_resources is not None:
            await consumer_resources.close()
    finally:
        consumer_resources = None
        cart_event_consumer = None
    logger.info("Cart event consumer resources closed.")


# Queue that receives order lifecycle events relevant to the cart.
# Binds to order.created and order.confirmed so the cart can be cleared
# when a purchase is finalized.
cart_order_events_queue = topology.queue(
    name=CartEventsQueue.CART_ORDER_EVENTS_QUEUE,
    routing_key="order.*",
    dead_letter_key=CartEventsQueue.CART_ORDER_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=cart_order_events_queue.queue, exchange=order_exchange)
async def handle_cart_order_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """
    FastStream subscriber that delegates order events to CartEventConsumer.

    The consumer listens to order.created (and order.confirmed as a safety-net)
    and clears the corresponding user's shopping cart.
    """
    if cart_event_consumer is None:
        raise RuntimeError("Cart event consumer received a message before startup completed.")
    handler = cart_event_consumer  # narrowed to non-None for the lambda below
    await topology.dispatch(
        cart_order_events_queue,
        message,
        lambda: handler.handle_order_event(body),
    )
