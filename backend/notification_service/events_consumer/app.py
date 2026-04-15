from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import (
    logger,
    broker,
    notification_service_database_session_manager,
)
from .event_handlers import user_handler, order_handler
from shared.enums.event_enums import UserEventsQueue, OrderEventsQueue


"""
The FastStream app (app) will be executed by faststream run via the command line,
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it
connects directly to RabbitMQ
"""


app = FastStream(broker)


@app.on_startup
async def startup():
    await notification_service_database_session_manager.init_db()
    logger.info("Notification consumer: database initialized.")


@app.on_shutdown
async def shutdown():
    await notification_service_database_session_manager.close()
    logger.info("Notification consumer: database connection closed.")


# Queue definitions
user_events_queue = RabbitQueue(
    UserEventsQueue.USER_EVENTS_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": UserEventsQueue.USER_EVENTS_DEAD_LETTER_QUEUE,
    },
)

order_events_queue = RabbitQueue(
    OrderEventsQueue.ORDER_EVENTS_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": OrderEventsQueue.ORDER_EVENTS_DEAD_LETTER_QUEUE,
    },
)

# Subscribers
handle_user_events = broker.subscriber(queue=user_events_queue)(user_handler.handle)
handle_order_events = broker.subscriber(queue=order_events_queue)(order_handler.handle)
