from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from service_config import logger, settings
from events_consumer.cart_event_consumer import CartEventConsumer
from events_consumer.runtime import CartConsumerResources, create_cart_consumer_resources
from shared.enums.event_enums import CartEventsQueue


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
order_exchange = RabbitExchange(
    name="order.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
app = FastStream(rabbitmq_broker)
consumer_resources: CartConsumerResources | None = None
cart_event_consumer: CartEventConsumer | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, cart_event_consumer
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
    if cart_event_consumer is None:
        raise RuntimeError("Cart event consumer received a message before startup completed.")
    await cart_event_consumer.handle_order_event(body)
