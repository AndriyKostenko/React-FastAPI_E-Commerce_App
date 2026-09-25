from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage

from service_config import logger, settings
from events_consumer.runtime import (
    WishlistConsumerResources,
    create_wishlist_consumer_resources,
)
from events_consumer.wishlist_event_consumer import WishlistEventConsumer
from shared.enums.event_enums import WishlistEventsQueue
from shared.messaging import ConsumerTopology


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
user_exchange = RabbitExchange(
    name="user.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)
consumer_resources: WishlistConsumerResources | None = None
wishlist_event_consumer: WishlistEventConsumer | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, wishlist_event_consumer
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
    consumer_resources = create_wishlist_consumer_resources()
    try:
        await consumer_resources.start()
    except Exception:
        await consumer_resources.close()
        consumer_resources = None
        raise
    wishlist_event_consumer = WishlistEventConsumer(
        logger=consumer_resources.logger,
        settings=consumer_resources.settings,
        database=consumer_resources.database,
        idempotency=consumer_resources.idempotency,
    )
    logger.info("Wishlist event consumer resources started.")


@app.on_shutdown
async def shutdown() -> None:
    global consumer_resources, wishlist_event_consumer
    try:
        if consumer_resources is not None:
            await consumer_resources.close()
    finally:
        consumer_resources = None
        wishlist_event_consumer = None
    logger.info("Wishlist event consumer resources closed.")


# Queue that receives user lifecycle events relevant to the wishlist.
# Binds to user.deleted so the wishlist can be cleaned up when a user is removed.
wishlist_user_events_queue = topology.queue(
    name=WishlistEventsQueue.WISHLIST_EVENTS_QUEUE,
    routing_key="user.deleted",
    dead_letter_key=WishlistEventsQueue.WISHLIST_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=wishlist_user_events_queue.queue, exchange=user_exchange)
async def handle_wishlist_user_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """
    FastStream subscriber that delegates user events to WishlistEventConsumer.

    The consumer listens to user.deleted and removes the corresponding wishlist.
    """
    if wishlist_event_consumer is None:
        raise RuntimeError("Wishlist event consumer received a message before startup completed.")
    handler = wishlist_event_consumer  # narrowed to non-None for the lambda below
    await topology.dispatch(
        wishlist_user_events_queue,
        message,
        lambda: handler.handle_user_event(body),
    )
