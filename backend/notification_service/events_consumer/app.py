from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from .event_handlers import UserEventHandler, OrderEventHandler, PaymentEventHandler
from shared.enums.event_enums import UserEventsQueue, OrderEventsQueue, PaymentEventsQueue
from resources import (
    NotificationConsumerResources,
    create_notification_consumer_resources,
    logger,
    settings,
)
from tasks.broker import taskiq_broker


"""
The FastStream app (app) will be executed by faststream run via the command line,
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it
connects directly to RabbitMQ
"""


rabbitmq_broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
user_exchange = RabbitExchange(name="user.events.exchange", durable=True, type=ExchangeType.TOPIC)
order_exchange = RabbitExchange(name="order.events.exchange", durable=True, type=ExchangeType.TOPIC)
payment_exchange = RabbitExchange(name="payment.events.exchange", durable=True, type=ExchangeType.TOPIC)
app = FastStream(rabbitmq_broker)

user_handler: UserEventHandler | None = None
order_handler: OrderEventHandler | None = None
payment_handler: PaymentEventHandler | None = None
consumer_resources: NotificationConsumerResources | None = None
taskiq_started = False


@app.on_startup
async def startup():
    global consumer_resources, taskiq_started
    global user_handler, order_handler, payment_handler
    resources = create_notification_consumer_resources()
    taskiq_start_attempted = False
    started_taskiq = False
    try:
        await resources.start()
        taskiq_start_attempted = True
        await taskiq_broker.startup()
        started_taskiq = True
        new_user_handler = UserEventHandler(
            resources.idempotency,
            resources.database,
            resources.logger,
        )
        new_order_handler = OrderEventHandler(
            resources.idempotency,
            resources.database,
            resources.logger,
        )
        new_payment_handler = PaymentEventHandler(
            resources.idempotency,
            resources.database,
            resources.logger,
        )
    except Exception:
        try:
            if taskiq_start_attempted:
                await taskiq_broker.shutdown()
        finally:
            await resources.close()
        raise

    consumer_resources = resources
    taskiq_started = started_taskiq
    user_handler = new_user_handler
    order_handler = new_order_handler
    payment_handler = new_payment_handler
    logger.info("Notification consumer: schema is managed by Alembic migrations.")


@app.on_shutdown
async def shutdown():
    global consumer_resources, taskiq_started
    global user_handler, order_handler, payment_handler
    resources = consumer_resources
    should_stop_taskiq = taskiq_started
    consumer_resources = None
    taskiq_started = False
    user_handler = order_handler = payment_handler = None
    try:
        if should_stop_taskiq:
            await taskiq_broker.shutdown()
    finally:
        if resources is not None:
            await resources.close()
    logger.info("Notification consumer: database connection closed.")


# Queue definitions — bound to their respective TOPIC exchanges via routing key patterns.
# user.# matches: user.registered, user.logged.in, user.email.verified, etc.
# order.# matches: order.created, order.confirmed, order.cancelled
user_events_queue = RabbitQueue(
    UserEventsQueue.USER_EVENTS_QUEUE, # declares a queue bound to user.events.exchange TOPIC
    durable=True,
    routing_key="user.#", # matches all user-related events, but we only handle user.registered, user.logged.in, and user.email.verified for notifications. password.reset.* events are ignored.
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": UserEventsQueue.USER_EVENTS_DEAD_LETTER_QUEUE,
    },
)

order_events_queue = RabbitQueue(
    OrderEventsQueue.ORDER_EVENTS_QUEUE, # declares a queue bound to order.events.exchange TOPIC
    durable=True,
    routing_key="order.#", # matches all order-related events, but we only handle order.confirmed and order.cancelled for notifications. order.created is ignored.
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": OrderEventsQueue.ORDER_EVENTS_DEAD_LETTER_QUEUE,
    },
)

payment_events_queue = RabbitQueue(
    PaymentEventsQueue.PAYMENT_EVENTS_QUEUE, # declares a queue bound to payment.events.exchange TOPIC
    durable=True,
    routing_key="payment.#",
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": PaymentEventsQueue.PAYMENT_EVENTS_DEAD_LETTER_QUEUE,
    },
)

# Subscribers — exchange param wires up the queue binding on startup
@rabbitmq_broker.subscriber(queue=user_events_queue, exchange=user_exchange)
async def handle_user_events(body: dict[str, Any]) -> None:
    if user_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    await user_handler.handle(body)


@rabbitmq_broker.subscriber(queue=order_events_queue, exchange=order_exchange)
async def handle_order_events(body: dict[str, Any]) -> None:
    if order_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    await order_handler.handle(body)


@rabbitmq_broker.subscriber(queue=payment_events_queue, exchange=payment_exchange)
async def handle_payment_events(body: dict[str, Any]) -> None:
    if payment_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    await payment_handler.handle(body)
