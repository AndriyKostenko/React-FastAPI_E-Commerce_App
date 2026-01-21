from uuid import uuid4
from logging import Logger
from datetime import datetime, timezone

from pydantic import EmailStr
from faststream.rabbit import RabbitQueue

from shared.event_publisher import BaseEventPublisher
from shared.settings import Settings
from shared.shared_instances import settings, logger
from shared.schemas.event_schemas import (
    UserRegisteredEvent,
    UserLoginEvent,
    PasswordResetRequestedEvent,
    PasswordResetSuccessEvent
)


class NotificationEventdPublisher(BaseEventPublisher):
    def __init__(self, settings: Settings, logger: Logger) -> None:
        super().__init__(logger, settings)
        self.user_events_queue: RabbitQueue = RabbitQueue("user.events", durable=True)
        self.notification_events_queue: RabbitQueue = RabbitQueue("notification.events", durable=True)

    async def publish_user_registered(self, email: EmailStr, token: str):
        """Publish user registration event"""
        event = UserRegisteredEvent(
            email=email,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="api-gateway",
            token=token,
            event_type="user.registered"
        )
        await self.publish_an_event(
            message=event,
            queue=self.user_events_queue,
        )

    async def publish_user_login(self, email: EmailStr):
        """Publish user login event"""
        event = UserLoginEvent(
            email=email,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="api-gateway",
            event_type="user.logged.in"
        )
        await self.publish_an_event(
            message=event,
            queue=self.user_events_queue
        )

    async def publish_password_reset_request(self, email: EmailStr, reset_token: str):
        """Publish user password reset request"""
        event = PasswordResetRequestedEvent(
            email=email,
            reset_token=reset_token,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="api-gateway",
            event_type="user.password.reset.request"
        )
        await self.publish_an_event(
            message=event,
            queue=self.user_events_queue
        )

    async def publish_password_reset_seccess(self, email: EmailStr):
        event = PasswordResetSuccessEvent(
            email=email,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="api-gateway",
            event_type="user.password.reset.success"
        )
        await self.publish_an_event(
            message=event,
            queue=self.user_events_queue
        )


notification_events_publisher = NotificationEventdPublisher(settings, logger)
