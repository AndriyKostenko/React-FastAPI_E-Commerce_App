from typing import Dict, Any

from shared.email_service import email_service
from shared.schemas.event_schemas import UserRegisteredEvent, PasswordResetRequestedEvent
from ..main import user_events_queue, broker



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

