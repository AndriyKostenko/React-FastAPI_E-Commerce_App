from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, supplier_exchange
from shared.enums.event_enums import ProductSupplierEventsQueue, SupplierEvents
from event_consumer.supplier_event_consumer import supplier_event_consumer


# FastStream app for supplier_service consumers
app = FastStream(rabbitmq_broker)

# Listen for product_service import feedback events
product_supplier_events_queue = RabbitQueue(
    ProductSupplierEventsQueue.PRODUCT_SUPPLIER_EVENTS_QUEUE,
    durable=True,
    routing_key="supplier.product.import.*",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": ProductSupplierEventsQueue.PRODUCT_SUPPLIER_EVENTS_DEAD_LETTER_QUEUE,
    },
)


@rabbitmq_broker.subscriber(queue=product_supplier_events_queue, exchange=supplier_exchange)
async def handle_product_supplier_events(body: dict[str, Any]):
    """Handle import feedback events from product_service."""
    await supplier_event_consumer.handle_import_feedback_event(body)
