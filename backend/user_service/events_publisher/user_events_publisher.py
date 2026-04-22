from logging import Logger
from uuid import UUID

from pydantic import EmailStr
from faststream.rabbit import RabbitExchange

from shared.events.event_publisher import BaseEventPublisher
from shared.schemas.event_schemas import (
    PasswordResetRequestedEvent,
    PasswordResetSuccessEvent,
    UserLoginEvent,
    UserRegisteredEvent,
    EmailVerificationEvent
)
from shared.settings import Settings
from shared.shared_instances import rabbitmq_broker, logger, settings, user_exchange


class UserEventPublisher(BaseEventPublisher):
    """
    Event publisher for user-related events
    Publishes events to the user.events.exchange with routing keys like:
    - user.registered
    - user.logged.in
    - user.password.reset.requested
    - user.password.reset.success
    - user.email.verified
    """
    def __init__(self, logger: Logger, settings: Settings) -> None:
        super().__init__(rabbitmq_broker, logger, settings)
        self.exchange: RabbitExchange = user_exchange

    async def publish_user_registered(self, email: EmailStr, token: str, user_id: UUID | None = None) -> None:
        """Publish user registration event"""
        event = UserRegisteredEvent(user_email=email, token=token, user_id=user_id)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published user.registered event for {email}")

    async def publish_user_logged_in(self, email: EmailStr, user_id: UUID | None = None) -> None:
        """Publish user login event"""
        event = UserLoginEvent(user_email=email, user_id=user_id)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published user.logged.in event for {email}")

    async def publish_password_reset_request(self, email: EmailStr, reset_token: str, user_id: UUID | None = None) -> None:
        """Publish user password reset request"""
        event = PasswordResetRequestedEvent(user_email=email, reset_token=reset_token, user_id=user_id)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published password.reset.requested event for {email}")

    async def publish_password_reset_success(self, email: EmailStr, user_id: UUID | None = None):
        event = PasswordResetSuccessEvent(user_email=email, user_id=user_id)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published password.reset.success event for {email}")

    async def publish_email_verified(self, email: EmailStr, user_id: UUID | None = None):
        event = EmailVerificationEvent(user_email=email, user_id=user_id)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published email.verified event for {email}")


user_events_publisher = UserEventPublisher(logger=logger, settings=settings)
