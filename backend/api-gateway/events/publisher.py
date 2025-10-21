from uuid import UUID, uuid4
from datetime import datetime, timezone

from faststream.rabbit import RabbitBroker, RabbitQueue #type: ignore
from pydantic import EmailStr

from shared.shared_instances import settings, logger
from shared.schemas.event_schemas import UserRegisteredEvent, UserLoginEvent, PasswordResetRequestedEvent,  PasswordResetSuccessEvent


# Creating the broker 
broker = RabbitBroker(settings.RABBITMQ_BROKER_URL)

# Define queues
user_events_queue = RabbitQueue("user.events", durable=True)
notification_events_queue = RabbitQueue("notification.events", durable=True)


class ApiGatewayEventPublisher:
    """Event publisher for API Gateway using FastStream"""
    
    def __init__(self, logger):
        self.broker = broker
        self._is_started = False
        self.logger = logger
    
    async def start(self):
        """Start the broker connection"""
        if not self._is_started:
            await self.broker.start()
            self._is_started = True
            self.logger.info("API Gateway event publisher started")

    async def stop(self):
        """Stop the broker connection"""
        if self._is_started:
            await self.broker.close()
            self._is_started = False
            self.logger.info("API Gateway event publisher stopped")

    async def publish_an_event(self, message: dict, queue: RabbitQueue):
        """Generic method to publish an event"""
        await self.broker.publish(
            message=message,
            queue=queue,
        )
        self.logger.info(f"Published event to: {queue}")

    async def publish_user_registered(self, email: str, token: str):
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
            message=event.model_dump(),
            queue=user_events_queue,
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
            message=event.model_dump(),
            queue=user_events_queue
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
            message=event.model_dump(),
            queue=user_events_queue
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
            message=event.model_dump(),
            queue=user_events_queue
        )
        
        
        
events_publisher = ApiGatewayEventPublisher(logger=logger)
    
        
