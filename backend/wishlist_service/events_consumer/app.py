from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, user_exchange
from events_consumer.wishlist_event_consumer import wishlist_event_consumer
from shared.enums.event_enums import WishlistEventsQueue


# Create the FastStream app
app = FastStream(rabbitmq_broker)


# Queue that receives user lifecycle events relevant to the wishlist.
# Binds to user.deleted so the wishlist can be cleaned up when a user is removed.
wishlist_user_events_queue = RabbitQueue(
    name=WishlistEventsQueue.WISHLIST_EVENTS_QUEUE,
    durable=True,
    routing_key="user.deleted",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": WishlistEventsQueue.WISHLIST_EVENTS_DEAD_LETTER_QUEUE,
    },
)


@rabbitmq_broker.subscriber(queue=wishlist_user_events_queue, exchange=user_exchange)
async def handle_wishlist_user_events(body: dict[str, Any]) -> None:
    """
    FastStream subscriber that delegates user events to WishlistEventConsumer.

    The consumer listens to user.deleted and removes the corresponding wishlist.
    """
    await wishlist_event_consumer.handle_user_event(body)
