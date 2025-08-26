from faststream import FastStream # type: ignore
from faststream.rabbit import RabbitBroker, RabbitQueue # type: ignore

from typing import Dict, Any
from shared.shared_instances import logger, settings
from service_layer.email_service import email_service
from shared.schemas.event_schemas import UserRegisteredEvent, PasswordResetRequestedEvent


"""
The FastStream app (app) will be executed by faststream run via the command line, 
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it 
connects directly to RabbitMQ

For now its stated in notification-service microservice, but later on can be moved to a separate microservice
"""


# Create the broker and FastStream app
broker = RabbitBroker(settings.RABBITMQ_BROKER_URL)
app = FastStream(broker, title="Notification Service Consumer")

# Define queues and their dead-letter settings
user_events_queue = RabbitQueue("user.events", durable=True, arguments={"x-dead-letter-exchange": "dlx", "x-dead-letter-routing-key": "user.events.dlq"})
notification_events_queue = RabbitQueue("notification.events", durable=True, arguments={"x-dead-letter-exchange": "dlx", "x-dead-letter-routing-key": "notification.events.dlq"})


@broker.subscriber(user_events_queue, retry=3)
async def handle_user_events(message: Dict[str, Any]):
    """Handle user registration and password reset events"""
    match message.get("routing_key"):
        case "user.registered":
            event = UserRegisteredEvent(**message)
            await email_service.send_verification_email(**event.model_dump())
        case "user.login":
            event = PasswordResetRequestedEvent(**message)
            await email_service.send_password_reset_email(**event.model_dump())

