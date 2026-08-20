from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from shared.enums.event_enums import OrderEvents, ProductSupplierEventsQueue
from event_consumer.supplier_event_consumer import SupplierEventConsumer
from resources import (
    SupplierConsumerResources,
    create_supplier_consumer_resources,
    logger,
    settings,
)


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
supplier_exchange = RabbitExchange("supplier.events.exchange", durable=True, type=ExchangeType.TOPIC)
order_exchange = RabbitExchange("order.events.exchange", durable=True, type=ExchangeType.TOPIC)
inventory_exchange = RabbitExchange("inventory.events.exchange", durable=True, type=ExchangeType.TOPIC)
app = FastStream(rabbitmq_broker)

supplier_event_consumer: SupplierEventConsumer | None = None
consumer_resources: SupplierConsumerResources | None = None


@app.on_startup
async def startup() -> None:
    global consumer_resources, supplier_event_consumer
    resources = create_supplier_consumer_resources(
        broker=rabbitmq_broker,
        supplier_exchange=supplier_exchange,
        order_exchange=order_exchange,
        inventory_exchange=inventory_exchange,
    )
    try:
        await resources.start()
        consumer = SupplierEventConsumer(
            logger=resources.logger,
            settings=resources.settings,
            database=resources.database,
            idempotency_service=resources.idempotency,
            cj_api_client=resources.cj_api_client,
            product_service_client=resources.product_service_client,
            publisher=resources.publisher,
        )
    except Exception:
        await resources.close()
        raise
    consumer_resources = resources
    supplier_event_consumer = consumer


@app.on_shutdown
async def shutdown() -> None:
    global consumer_resources, supplier_event_consumer
    resources = consumer_resources
    consumer_resources = None
    supplier_event_consumer = None
    if resources is not None:
        await resources.close()


def get_consumer() -> SupplierEventConsumer:
    if supplier_event_consumer is None:
        raise RuntimeError("Supplier consumer resources are not initialized")
    return supplier_event_consumer


# Supplier-service–specific queue for import-feedback events
# (supplier.product.import.completed / supplier.product.import.failed).
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
    await get_consumer().handle_import_feedback_event(body)


@rabbitmq_broker.subscriber(queue=order_confirmed_queue, exchange=order_exchange)
async def handle_order_confirmed(body: dict[str, Any]):
    await get_consumer().handle_order_event(body)
