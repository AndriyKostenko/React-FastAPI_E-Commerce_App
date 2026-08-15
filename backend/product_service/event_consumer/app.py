from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from shared.enums.event_enums import ProductInventoryEventsQueue, ProductSupplierEventsQueue, SupplierEvents
from event_consumer.product_event_consumer import ProductEventConsumer
from resources import (
    ProductConsumerResources,
    create_product_consumer_resources,
    logger,
    settings,
)


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
inventory_exchange = RabbitExchange(
    name="inventory.events.exchange", durable=True, type=ExchangeType.TOPIC
)
supplier_exchange = RabbitExchange(
    name="supplier.events.exchange", durable=True, type=ExchangeType.TOPIC
)
app = FastStream(rabbitmq_broker)

product_event_consumer: ProductEventConsumer | None = None
consumer_resources: ProductConsumerResources | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, product_event_consumer
    resources = create_product_consumer_resources(
        broker=rabbitmq_broker,
        inventory_exchange=inventory_exchange,
        supplier_exchange=supplier_exchange,
    )
    try:
        await resources.start()
        consumer = ProductEventConsumer(
            logger=resources.logger,
            database=resources.database,
            idempotency_service=resources.idempotency,
            cache_manager=resources.cache,
            publisher=resources.publisher,
        )
    except Exception:
        await resources.close()
        raise
    consumer_resources = resources
    product_event_consumer = consumer


@app.on_shutdown
async def shutdown() -> None:
    global consumer_resources, product_event_consumer
    resources = consumer_resources
    consumer_resources = None
    product_event_consumer = None
    if resources is not None:
        await resources.close()


def get_consumer() -> ProductEventConsumer:
    if product_event_consumer is None:
        raise RuntimeError("Product consumer resources are not initialized")
    return product_event_consumer

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
    await get_consumer().handle_inventory_saga_event(body)


@rabbitmq_broker.subscriber(queue=product_supplier_events_queue, exchange=supplier_exchange)
async def handle_supplier_events(body: dict[str, Any]):
    await get_consumer().handle_supplier_products_fetched(body)
