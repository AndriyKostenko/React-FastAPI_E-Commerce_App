from typing import Any

from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage

from .event_handlers import (
    CJOrderEventHandler,
    OrderEventHandler,
    PaymentEventHandler,
    ProductionEventHandler,
    UserEventHandler,
)
from shared.enums.event_enums import (
    OrderEventsQueue,
    PaymentEventsQueue,
    ProductionEventsQueue,
    UserEventsQueue,
)
from shared.messaging import ConsumerTopology
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
# Owns every queue below plus their retry queues and DLQs.
topology = ConsumerTopology(rabbitmq_broker, logger)

user_handler: UserEventHandler | None = None
order_handler: OrderEventHandler | None = None
payment_handler: PaymentEventHandler | None = None
cj_order_handler: CJOrderEventHandler | None = None
production_handler: ProductionEventHandler | None = None
consumer_resources: NotificationConsumerResources | None = None
taskiq_started = False


@app.on_startup
async def startup():
    global consumer_resources, taskiq_started
    global user_handler, order_handler, payment_handler, cj_order_handler, production_handler
    # Before the broker starts consuming, so no failure can dead-letter into
    # an exchange that does not exist yet.
    await topology.declare()
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
        new_cj_order_handler = CJOrderEventHandler(
            resources.idempotency,
            resources.database,
            resources.logger,
        )
        new_production_handler = ProductionEventHandler(
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
    cj_order_handler = new_cj_order_handler
    production_handler = new_production_handler
    logger.info("Notification consumer: schema is managed by Alembic migrations.")


@app.on_shutdown
async def shutdown():
    global consumer_resources, taskiq_started
    global user_handler, order_handler, payment_handler, cj_order_handler, production_handler
    resources = consumer_resources
    should_stop_taskiq = taskiq_started
    consumer_resources = None
    taskiq_started = False
    user_handler = order_handler = payment_handler = cj_order_handler = None
    production_handler = None
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
user_events_queue = topology.queue(
    name=UserEventsQueue.USER_EVENTS_QUEUE,
    routing_key="user.#", # matches all user-related events, but we only handle user.registered, user.logged.in, and user.email.verified for notifications. password.reset.* events are ignored.
    dead_letter_key=UserEventsQueue.USER_EVENTS_DEAD_LETTER_QUEUE,
)

order_events_queue = topology.queue(
    name=OrderEventsQueue.ORDER_EVENTS_QUEUE,
    routing_key="order.#", # matches all order-related events, but we only handle order.confirmed and order.cancelled for notifications. order.created is ignored.
    dead_letter_key=OrderEventsQueue.ORDER_EVENTS_DEAD_LETTER_QUEUE,
)

payment_events_queue = topology.queue(
    name=PaymentEventsQueue.PAYMENT_EVENTS_QUEUE,
    routing_key="payment.#",
    dead_letter_key=PaymentEventsQueue.PAYMENT_EVENTS_DEAD_LETTER_QUEUE,
)

# Subscribers — exchange param wires up the queue binding on startup
@rabbitmq_broker.subscriber(queue=user_events_queue.queue, exchange=user_exchange)
async def handle_user_events(body: dict[str, Any], message: RabbitMessage) -> None:
    if user_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    handler = user_handler  # narrowed to non-None for the lambda below
    await topology.dispatch(
        user_events_queue,
        message,
        lambda: handler.handle(body),
    )


@rabbitmq_broker.subscriber(queue=order_events_queue.queue, exchange=order_exchange)
async def handle_order_events(body: dict[str, Any], message: RabbitMessage) -> None:
    if order_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    handler = order_handler  # narrowed to non-None for the lambda below
    await topology.dispatch(
        order_events_queue,
        message,
        lambda: handler.handle(body),
    )


# CJ fulfillment events share the order exchange but use a "cj.order.*"
# routing key, which the "order.#" binding above does not match. Binding them
# on a separate queue keeps the two flows independently retryable.
cj_order_events_queue = topology.queue(
    name=OrderEventsQueue.NOTIFICATION_CJ_ORDER_EVENTS_QUEUE,
    routing_key="cj.order.#",
    dead_letter_key=OrderEventsQueue.NOTIFICATION_CJ_ORDER_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=cj_order_events_queue.queue, exchange=order_exchange)
async def handle_cj_order_events(body: dict[str, Any], message: RabbitMessage) -> None:
    if cj_order_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    handler = cj_order_handler  # narrowed to non-None for the lambda below
    await topology.dispatch(
        cj_order_events_queue,
        message,
        lambda: handler.handle(body),
    )


@rabbitmq_broker.subscriber(queue=payment_events_queue.queue, exchange=payment_exchange)
async def handle_payment_events(body: dict[str, Any], message: RabbitMessage) -> None:
    if payment_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    handler = payment_handler  # narrowed to non-None for the lambda below
    await topology.dispatch(
        payment_events_queue,
        message,
        lambda: handler.handle(body),
    )


# In-house fulfillment events share the order exchange but use a
# "production.job.*" routing key, which neither the "order.#" nor the
# "cj.order.#" binding above matches. A custom T-shirt is printed and posted
# by hand rather than by a carrier integration, so this queue carries the only
# dispatch notice the buyer of one ever gets.
production_events_queue = topology.queue(
    name=ProductionEventsQueue.NOTIFICATION_PRODUCTION_EVENTS_QUEUE,
    routing_key="production.job.#",
    dead_letter_key=ProductionEventsQueue.NOTIFICATION_PRODUCTION_EVENTS_DEAD_LETTER_QUEUE,
)


@rabbitmq_broker.subscriber(queue=production_events_queue.queue, exchange=order_exchange)
async def handle_production_events(body: dict[str, Any], message: RabbitMessage) -> None:
    if production_handler is None:
        raise RuntimeError("Notification consumer resources are not initialized")
    handler = production_handler  # narrowed to non-None for the lambda below
    await topology.dispatch(
        production_events_queue,
        message,
        lambda: handler.handle(body),
    )
