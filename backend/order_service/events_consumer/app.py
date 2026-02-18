from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue
from orjson import loads

from shared.shared_instances import broker
from events_consumer.order_event_consumer import order_event_consumer

# Create the FastStream app
app = FastStream(broker)


# Define the queue for SAGA responses from other services
order_saga_response_queue = RabbitQueue(
    "order.saga.response",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "order.saga.response.dlq"
    }
)


# Register the subscriber function (FastStream requires this at module level)
@broker.subscriber(queue=order_saga_response_queue)
async def handle_order_saga_responses(body: str):
    """
    FastStream subscriber function that delegates to the OrderEventConsumer class.
    This pattern gives us:
    - Class-based organization for business logic
    - Proper FastStream integration with decorators
    - Clean separation of concerns
    """
    message: dict[str, Any] = loads(body)
    await order_event_consumer.handle_order_saga_response(message)
