from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage

from contracts.event_enums import (
    ProductArtworkEventsQueue,
    ProductInventoryEventsQueue,
    ProductSupplierEventsQueue,
    ProductUserEventsQueue,
    SupplierEvents,
    UserEvents,
)
from infrastructure.messaging import ConsumerTopology
from event_consumer.account_deletion_consumer import AccountDeletionConsumer
from event_consumer.product_event_consumer import ProductEventConsumer
from resources import (
    ProductConsumerResources,
    create_deleted_account_cleanup,
    create_product_consumer_resources,
    create_supplier_image_review_service,
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
user_exchange = RabbitExchange(
    name="user.events.exchange", durable=True, type=ExchangeType.TOPIC
)
app = FastStream(rabbitmq_broker)
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)

product_event_consumer: ProductEventConsumer | None = None
account_deletion_consumer: AccountDeletionConsumer | None = None
consumer_resources: ProductConsumerResources | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, product_event_consumer, account_deletion_consumer
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
            image_review=create_supplier_image_review_service(resources.database, resources.http_session),
        )
        deletions = AccountDeletionConsumer(
            cleanup=create_deleted_account_cleanup(resources.database),
            idempotency_service=resources.idempotency,
            logger=resources.logger,
        )
    except Exception:
        await resources.close()
        raise
    consumer_resources = resources
    product_event_consumer = consumer
    account_deletion_consumer = deletions


@app.on_shutdown
async def shutdown() -> None:
    global consumer_resources, product_event_consumer, account_deletion_consumer
    resources = consumer_resources
    consumer_resources = None
    product_event_consumer = None
    account_deletion_consumer = None
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


# supplier.stock.updated - the hourly CJ stock refresh. Its own queue, so a
# long import batch never delays it and each stays independently retryable.
product_supplier_stock_queue = topology.queue(
    name=ProductSupplierEventsQueue.PRODUCT_SUPPLIER_STOCK_QUEUE,
    routing_key=SupplierEvents.SUPPLIER_STOCK_UPDATED,
    dead_letter_key=ProductSupplierEventsQueue.PRODUCT_SUPPLIER_STOCK_DLQ,
)


@rabbitmq_broker.subscriber(queue=product_supplier_stock_queue.queue, exchange=supplier_exchange)
async def handle_supplier_stock(body: dict[str, Any], message: RabbitMessage) -> None:
    await topology.dispatch(
        product_supplier_stock_queue,
        message,
        lambda: get_consumer().handle_supplier_stock_updated(body),
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


# A deleted account's unordered designs, and its id on refusal records.
product_user_events_queue = topology.queue(
    name=ProductUserEventsQueue.PRODUCT_USER_EVENTS_QUEUE,
    routing_key=UserEvents.USER_DELETED,
    dead_letter_key=ProductUserEventsQueue.PRODUCT_USER_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=product_user_events_queue.queue, exchange=user_exchange)
async def handle_user_events(body: dict[str, Any], message: RabbitMessage) -> None:
    if account_deletion_consumer is None:
        raise RuntimeError("Account deletion consumer received a message before startup completed.")
    handler = account_deletion_consumer  # narrowed to non-None for the lambda below
    await topology.dispatch(product_user_events_queue, message, lambda: handler.handle_user_event(body))
