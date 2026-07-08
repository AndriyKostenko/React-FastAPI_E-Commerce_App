from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import rabbitmq_broker, inventory_exchange, supplier_exchange
from shared.enums.event_enums import ProductInventoryEventsQueue, ProductSupplierEventsQueue, SupplierEvents
from event_consumer.product_event_consumer import product_event_consumer


# Create the FastStream app
app = FastStream(rabbitmq_broker)

# inventory.*.requested binds to inventory.reserve.requested and inventory.release.requested
product_inventory_events_queue = RabbitQueue(
    ProductInventoryEventsQueue.PRODUCT_INVENTORY_EVENTS_QUEUE,
    durable=True,
    routing_key="inventory.*.requested",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": ProductInventoryEventsQueue.PRODUCT_INVENTORY_EVENTS_DEAD_LETTER_QUEUE,
    },
)

# supplier.products.fetched - supplier_service emits products to be imported
product_supplier_events_queue = RabbitQueue(
    ProductSupplierEventsQueue.PRODUCT_SUPPLIER_EVENTS_QUEUE,
    durable=True,
    routing_key=SupplierEvents.SUPPLIER_PRODUCTS_FETCHED,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": ProductSupplierEventsQueue.PRODUCT_SUPPLIER_EVENTS_DEAD_LETTER_QUEUE,
    },
)


@rabbitmq_broker.subscriber(queue=product_inventory_events_queue, exchange=inventory_exchange)
async def handle_inventory_events(body: dict[str, Any]):
    await product_event_consumer.handle_inventory_saga_event(body)


@rabbitmq_broker.subscriber(queue=product_supplier_events_queue, exchange=supplier_exchange)
async def handle_supplier_events(body: dict[str, Any]):
    await product_event_consumer.handle_supplier_products_fetched(body)
