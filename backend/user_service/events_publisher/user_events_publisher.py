from datetime import datetime, timezone
from logging import Logger
from uuid import uuid4

from faststream.rabbit import RabbitQueue
from pydantic import EmailStr
from shared.event_publisher import BaseEventPublisher
from shared.schemas.event_schemas import (
    PasswordResetRequestedEvent,
    PasswordResetSuccessEvent,
    UserLoginEvent,
    UserRegisteredEvent
)
from shared.settings import Settings
from shared.shared_instances import broker, logger, settings


class NotificationEventPublisher(BaseEventPublisher):
    def __init__(self, logger: Logger, settings: Settings) -> None:
        super().__init__(broker, logger, settings)
        self.user_events_queue: RabbitQueue = RabbitQueue(
                    "user.events",
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": "dlx",
                        "x-dead-letter-routing-key": "user.events.dlq"
                    }
                )

    async def publish_user_registered(self, email: EmailStr, token: str) -> None:
        """Publish user registration event"""
        event = UserRegisteredEvent(
            user_email=email,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="user-service",
            token=token,
            event_type="user.registered",
        )
        await self.publish_an_event(
            message=event,
            queue=self.user_events_queue,
        )
        self.logger.info(f"Published user.registered event for {email}")

    async def publish_user_logged_in(self, email: EmailStr) -> None:
        """Publish user login event"""
        event = UserLoginEvent(
            user_email=email,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="user-service",
            event_type="user.logged.in",
        )
        await self.publish_an_event(message=event, queue=self.user_events_queue)
        self.logger.info(f"Published user.logged.in event for {email}")

    async def publish_password_reset_request(self, email: EmailStr, reset_token: str) -> None:
        """Publish user password reset request"""
        event = PasswordResetRequestedEvent(
            user_email=email,
            reset_token=reset_token,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="user-service",
            event_type="user.password.reset.request",
        )
        await self.publish_an_event(message=event, queue=self.user_events_queue)
        self.logger.info(f"Published password.reset.requested event for {email}")

    async def publish_password_reset_seccess(self, email: EmailStr):
        event = PasswordResetSuccessEvent(
            user_email=email,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="user-service",
            event_type="user.password.reset.success",
        )
        await self.publish_an_event(message=event, queue=self.user_events_queue)
        self.logger.info(f"Published password.reset.success event for {email}")


notification_events_publisher = NotificationEventPublisher(
    logger=logger, settings=settings
)
