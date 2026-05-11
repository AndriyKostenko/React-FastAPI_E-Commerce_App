from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, inventory_exchange
from shared.enums.event_enums import ProductInventoryEventsQueue
from event_consumer.product_event_consumer import product_event_consumer


# Create the FastStream app
app = FastStream(rabbitmq_broker)

# inventory.*.requested binds to inventory.reserve.requested and inventory.release.requested
product_inventory_events_queue = RabbitQueue(
    ProductInventoryEventsQueue.PRODUCT_INVENTORY_EVENTS_QUEUE,
    durable=True,
    routing_key="inventory.*.requested", # matches inventory.reserve.requested and inventory.release.requested, but ignores any future events that don't match this pattern (e.g., inventory.updated, inventory.checked)
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": ProductInventoryEventsQueue.PRODUCT_INVENTORY_EVENTS_DEAD_LETTER_QUEUE
    }
)

# Register the subscriber function (FastStream requires this at module level)
@rabbitmq_broker.subscriber(queue=product_inventory_events_queue, exchange=inventory_exchange)
async def handle_inventory_events(body: dict[str, Any]):
    """
    FastStream subscriber function that delegates to the OrderEventConsumer class.

    This pattern provides:
    - Class-based organization for complex business logic
    - Proper FastStream integration with decorators at module level
    - Clear separation of concerns
    - Easy testing (can test OrderEventConsumer independently)
    """
    await product_event_consumer.handle_inventory_saga_event(body)
