from typing import Any
from logging import Logger

from faststream.rabbit import RabbitExchange

from shared.events.event_publisher import BaseEventPublisher
from shared.schemas.event_schemas import (
    PasswordResetRequestedEvent,
    PasswordResetSuccessEvent,
    UserLoginEvent,
    UserRegisteredEvent,
    EmailVerificationEvent,
    UserDeletedEvent,
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

    async def publish_user_registered(self, event_data: dict[str, Any]) -> None:
        """Publish user registration event"""
        event = UserRegisteredEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published user.registered event for {event.user_email}")

    async def publish_user_logged_in(self, event_data: dict[str, Any]) -> None:
        """Publish user login event"""
        event = UserLoginEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published user.logged.in event for {event.user_email}")

    async def publish_password_reset_request(self, event_data: dict[str, Any]) -> None:
        """Publish user password reset request"""
        event = PasswordResetRequestedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published password.reset.requested event for {event.user_email}")

    async def publish_password_reset_success(self, event_data: dict[str, Any]):
        event = PasswordResetSuccessEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published password.reset.success event for {event.user_email}")

    async def publish_email_verified(self, event_data: dict[str, Any]):
        event = EmailVerificationEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published email.verified event for {event.user_email}")

    async def publish_user_deleted(self, event_data: dict[str, Any]):
        event = UserDeletedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.exchange, routing_key=event.event_type)
        self.logger.info(f"Published user.deleted event for {event.user_email}")


user_events_publisher = UserEventPublisher(logger=logger, settings=settings)
