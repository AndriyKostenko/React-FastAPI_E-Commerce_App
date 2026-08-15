from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from service_config import logger, settings
from events_consumer.runtime import (
    ShippingConsumerResources,
    create_shipping_consumer_resources,
)
from events_consumer.shipping_event_consumer import ShippingEventConsumer
from shared.enums.event_enums import ShippingEventsQueue


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
consumer_resources: ShippingConsumerResources | None = None
shipping_event_consumer: ShippingEventConsumer | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, shipping_event_consumer
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
    if shipping_event_consumer is None:
        raise RuntimeError("Shipping event consumer received a message before startup completed.")
    await shipping_event_consumer.handle_order_event(body)
