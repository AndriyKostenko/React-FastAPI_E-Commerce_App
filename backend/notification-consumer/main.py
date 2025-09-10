from datetime import datetime
from typing import Any

from faststream import FastStream # type: ignore
from faststream.rabbit import RabbitBroker, RabbitQueue # type: ignore

from shared.shared_instances import logger, settings, email_service
from shared.customized_json_response import JSONResponse
from shared.schemas.event_schemas import UserRegisteredEvent, PasswordResetRequestedEvent, UserLoginEvent


"""
The FastStream app (app) will be executed by faststream run via the command line, 
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it 
connects directly to RabbitMQ
"""


# Create the broker and FastStream app
broker = RabbitBroker(settings.RABBITMQ_BROKER_URL)
app = FastStream(broker, title="Notification Consumer Service")


# Define queues and their dead-letter settings
user_events_queue = RabbitQueue("user.events", durable=True, arguments={"x-dead-letter-exchange": "dlx", "x-dead-letter-routing-key": "user.events.dlq"})


@broker.subscriber(user_events_queue, retry=3)
async def handle_user_events(message: dict[str, Any]):
    """Handle user registration and password reset events"""
    match message.get("event_type"):
        case "user.registered":
            event = UserRegisteredEvent(**message)
            await email_service.send_verification_email(**event.model_dump())
        case "user.loggedin":
            event = UserLoginEvent(**message)
            await email_service.send_login_notification_email(**event.model_dump())
        case _:
            logger.warning(f"Unhandled event type: {message.get('event_type')}")


    
