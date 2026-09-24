from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage

from shared.enums.event_enums import (
    ProductArtworkEventsQueue,
    ProductInventoryEventsQueue,
    ProductSupplierEventsQueue,
    SupplierEvents,
)
from shared.messaging import ConsumerTopology
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
order_exchange = RabbitExchange(
    name="order.events.exchange", durable=True, type=ExchangeType.TOPIC
)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)

product_event_consumer: ProductEventConsumer | None = None
consumer_resources: ProductConsumerResources | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, product_event_consumer
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
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
            settings=resources.settings,
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
product_inventory_events_queue = topology.queue(
    name=ProductInventoryEventsQueue.PRODUCT_INVENTORY_EVENTS_QUEUE,
    routing_key="inventory.*.requested",
    dead_letter_key=ProductInventoryEventsQueue.PRODUCT_INVENTORY_EVENTS_DEAD_LETTER_QUEUE,
)

# supplier.products.fetched - supplier_service emits products to be imported
product_supplier_events_queue = topology.queue(
    name=ProductSupplierEventsQueue.PRODUCT_SUPPLIER_EVENTS_QUEUE,
    routing_key=SupplierEvents.SUPPLIER_PRODUCTS_FETCHED,
    dead_letter_key=ProductSupplierEventsQueue.PRODUCT_SUPPLIER_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=product_inventory_events_queue.queue, exchange=inventory_exchange)
async def handle_inventory_events(body: dict[str, Any], message: RabbitMessage) -> None:
    await topology.dispatch(
        product_inventory_events_queue,
        message,
        lambda: get_consumer().handle_inventory_saga_event(body),
    )


@rabbitmq_broker.subscriber(queue=product_supplier_events_queue.queue, exchange=supplier_exchange)
async def handle_supplier_events(body: dict[str, Any], message: RabbitMessage) -> None:
    await topology.dispatch(
        product_supplier_events_queue,
        message,
        lambda: get_consumer().handle_supplier_products_fetched(body),
    )


# Artwork retention markers travel on the order exchange under "artwork.*",
# which neither the "order.#" nor the "cj.order.*" binding matches, so they
# get their own queue and stay independently retryable.
product_artwork_events_queue = topology.queue(
    name=ProductArtworkEventsQueue.PRODUCT_ARTWORK_EVENTS_QUEUE,
    routing_key="artwork.*",
    dead_letter_key=ProductArtworkEventsQueue.PRODUCT_ARTWORK_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=product_artwork_events_queue.queue, exchange=order_exchange)
async def handle_artwork_events(body: dict[str, Any], message: RabbitMessage) -> None:
    """Keep a paid order's print files safe from the unreferenced-draft cleanup."""
    await topology.dispatch(
        product_artwork_events_queue,
        message,
        lambda: get_consumer().handle_artwork_retention_event(body),
    )
