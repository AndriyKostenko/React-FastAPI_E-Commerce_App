from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue
from orjson import loads

from shared.shared_instances import rabbitmq_broker, inventory_exchange, payment_exchange
from events_consumer.order_event_consumer import order_event_consumer
from shared.enums.event_enums import OrderSagaResponseQueue, PaymentEvents


# Create the FastStream app
app = FastStream(rabbitmq_broker)


# inventory.reserve.* binds to inventory.reserve.succeeded and inventory.reserve.failed
order_saga_response_queue = RabbitQueue(
    name=OrderSagaResponseQueue.ORDER_SAGA_RESPONSE_QUEUE,
    durable=True,
    routing_key="inventory.reserve.*", # Listen to both success and failure of inventory reservation
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": OrderSagaResponseQueue.ORDER_SAGA_RESPONSE_DEAD_LETTER_QUEUE
    }
)

# Listens for payment.failed so the order can be cancelled when Stripe reports a failure
order_payment_events_queue = RabbitQueue(
    name="order.payment.events.queue",
    durable=True,
    routing_key=PaymentEvents.PAYMENT_FAILED,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "order.payment.events.dlq",
    },
)


# Register the subscriber function (FastStream requires this at module level)
@rabbitmq_broker.subscriber(queue=order_saga_response_queue, exchange=inventory_exchange)
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


@rabbitmq_broker.subscriber(queue=order_payment_events_queue, exchange=payment_exchange)
async def handle_order_payment_events(body: str) -> None:
    """
    FastStream subscriber for payment events that affect order state.
    Routes payment.failed to handle_payment_failed so the order is cancelled
    and any reserved inventory is released.
    """
    message: dict[str, Any] = loads(body)
    await order_event_consumer.handle_payment_event(message)
