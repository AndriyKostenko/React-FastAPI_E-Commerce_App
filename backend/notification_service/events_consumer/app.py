from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import (
    logger,
    rabbitmq_broker,
    notification_service_database_session_manager,
    user_exchange,
    order_exchange,
)
from .event_handlers import user_handler, order_handler
from shared.enums.event_enums import UserEventsQueue, OrderEventsQueue


"""
The FastStream app (app) will be executed by faststream run via the command line,
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it
connects directly to RabbitMQ
"""


app = FastStream(rabbitmq_broker)


@app.on_startup
async def startup():
    await notification_service_database_session_manager.init_db()
    logger.info("Notification consumer: database initialized.")


@app.on_shutdown
async def shutdown():
    await notification_service_database_session_manager.close()
    logger.info("Notification consumer: database connection closed.")


# Queue definitions — bound to their respective TOPIC exchanges via routing key patterns.
# user.# matches: user.registered, user.logged.in, user.email.verified, etc.
# order.# matches: order.created, order.confirmed, order.cancelled
user_events_queue = RabbitQueue(
    UserEventsQueue.USER_EVENTS_QUEUE,
    durable=True,
    routing_key="user.#", # matches all user-related events, but we only handle user.registered, user.logged.in, and user.email.verified for notifications. password.reset.* events are ignored.
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": UserEventsQueue.USER_EVENTS_DEAD_LETTER_QUEUE,
    },
)

order_events_queue = RabbitQueue(
    OrderEventsQueue.ORDER_EVENTS_QUEUE,
    durable=True,
    routing_key="order.#", # matches all order-related events, but we only handle order.confirmed and order.cancelled for notifications. order.created is ignored.
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": OrderEventsQueue.ORDER_EVENTS_DEAD_LETTER_QUEUE,
    },
)

# Subscribers — exchange param wires up the queue binding on startup
handle_user_events = rabbitmq_broker.subscriber(queue=user_events_queue, exchange=user_exchange)(user_handler.handle)
handle_order_events = rabbitmq_broker.subscriber(queue=order_events_queue, exchange=order_exchange)(order_handler.handle)
