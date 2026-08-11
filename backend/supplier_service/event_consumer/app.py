from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, supplier_exchange, order_exchange
from shared.enums.event_enums import OrderEvents, ProductSupplierEventsQueue
from event_consumer.supplier_event_consumer import supplier_event_consumer


# Create the FastStream app
app = FastStream(rabbitmq_broker)


# Supplier-service–specific queue for import-feedback events
# (supplier.product.import.succeeded / supplier.product.import.failed).
# Must NOT share the name "product.supplier.events" with product_service —
# that would cause RabbitMQ to merge both services' bindings on a single
# physical queue and drop ~50 % of messages in each direction.
product_supplier_events_queue = RabbitQueue(
    ProductSupplierEventsQueue.SUPPLIER_FEEDBACK_EVENTS_QUEUE,
    durable=True,
    routing_key="supplier.product.import.*",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": ProductSupplierEventsQueue.SUPPLIER_FEEDBACK_EVENTS_DLQ,
    },
)


order_confirmed_queue = RabbitQueue(
    "supplier.order.confirmed.queue",
    durable=True,
    routing_key=OrderEvents.ORDER_CONFIRMED,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "supplier.order.confirmed.dlq",
    },
)


@rabbitmq_broker.subscriber(queue=product_supplier_events_queue, exchange=supplier_exchange)
async def handle_product_supplier_events(body: dict[str, Any]):
    await supplier_event_consumer.handle_import_feedback_event(body)


@rabbitmq_broker.subscriber(queue=order_confirmed_queue, exchange=order_exchange)
async def handle_order_confirmed(body: dict[str, Any]):
    await supplier_event_consumer.handle_order_event(body)
