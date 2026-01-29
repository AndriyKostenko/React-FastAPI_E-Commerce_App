from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import broker
from event_consumer.product_event_consumer import product_event_consumer


# Create the FastStream app
app = FastStream(broker)

# Define the queue for SAGA responses from other services
product_inventory_events_queue = RabbitQueue(
    "product.inventory.events",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "product.inventory.events.dlq"
    }
)

# Register the subscriber function (FastStream requires this at module level)
@broker.subscriber(product_inventory_events_queue)
async def handle_inventory_events(event: dict[str, Any]):
    """
    FastStream subscriber function that delegates to the OrderEventConsumer class.

    This pattern provides:
    - Class-based organization for complex business logic
    - Proper FastStream integration with decorators at module level
    - Clear separation of concerns
    - Easy testing (can test OrderEventConsumer independently)
    """
    await product_event_consumer.handle_inventory_saga_event(event=event)
