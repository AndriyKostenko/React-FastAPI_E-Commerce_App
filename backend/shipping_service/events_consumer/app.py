from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage

from service_config import logger, settings
from events_consumer.runtime import (
    ShippingConsumerResources,
    create_shipping_consumer_resources,
)
from events_consumer.shipping_event_consumer import ShippingEventConsumer
from shared.enums.event_enums import ShippingEventsQueue
from shared.messaging import ConsumerTopology


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
order_exchange = RabbitExchange(
    name="order.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
shipping_exchange = RabbitExchange(
    name="shipping.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)
consumer_resources: ShippingConsumerResources | None = None
shipping_event_consumer: ShippingEventConsumer | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, shipping_event_consumer
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
    consumer_resources = create_shipping_consumer_resources(
        broker=rabbitmq_broker,
        shipping_exchange=shipping_exchange,
    )
    try:
        await consumer_resources.start()
    except Exception:
        await consumer_resources.close()
        consumer_resources = None
        raise
    shipping_event_consumer = ShippingEventConsumer(
        logger=consumer_resources.logger,
        database=consumer_resources.database,
        idempotency=consumer_resources.idempotency,
        event_publisher=consumer_resources.event_publisher,
    )
    logger.info("Shipping event consumer resources started.")


@app.on_shutdown
async def shutdown() -> None:
    global consumer_resources, shipping_event_consumer
    try:
        if consumer_resources is not None:
            await consumer_resources.close()
    finally:
        consumer_resources = None
        shipping_event_consumer = None
    logger.info("Shipping event consumer resources closed.")


shipping_order_events_queue = topology.queue(
    name=ShippingEventsQueue.SHIPPING_EVENTS_QUEUE,
    routing_key="order.*",
    dead_letter_key=ShippingEventsQueue.SHIPPING_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=shipping_order_events_queue.queue, exchange=order_exchange)
async def handle_shipping_order_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """Consume order lifecycle events relevant to shipping."""
    if shipping_event_consumer is None:
        raise RuntimeError("Shipping event consumer received a message before startup completed.")
    handler = shipping_event_consumer  # narrowed to non-None for the lambda below
    await topology.dispatch(
        shipping_order_events_queue,
        message,
        lambda: handler.handle_order_event(body),
    )
