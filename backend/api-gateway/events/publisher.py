from uuid import UUID, uuid4
from datetime import datetime, timezone

from faststream.rabbit import RabbitBroker, RabbitQueue # type: ignore

from shared.shared_instances import settings, logger
from shared.schemas.event_schemas import UserRegisteredEvent, UserLoginEvent


# Creating the broker 
broker = RabbitBroker(settings.RABBITMQ_BROKER_URL)

# Define queues
user_events_queue = RabbitQueue("user.events", durable=True)
notification_events_queue = RabbitQueue("notification.events", durable=True)


class ApiGatewayEventPublisher:
    """Event publisher for API Gateway using FastStream"""
    
    def __init__(self):
        self.broker = broker
        self._is_started = False
    
    async def start(self):
        """Start the broker connection"""
        if not self._is_started:
            await self.broker.start()
            self._is_started = True
            logger.info("API Gateway event publisher started")
    
    async def stop(self):
        """Stop the broker connection"""
        if self._is_started:
            await self.broker.close()
            self._is_started = False
            logger.info("API Gateway event publisher stopped")
    
    async def publish_user_registered(self, user_id: UUID, email: str, role: str, token: str):
        """Publish user registration event"""
        event = UserRegisteredEvent(
            user_id=user_id,
            email=email,
            role=role,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="api-gateway",
            token=token
        )
        
        await self.broker.publish(
            event=event.model_dump(),
            queue=user_events_queue,
            routing_key="user.registered"
        )
        logger.info(f"Published user registration event for: {email}")
        
    async def publish_user_login(self, user_id: UUID, email: str, role: str):
        """Publish user login event"""
        event = UserLoginEvent(
            user_id=user_id,
            email=email,
            role=role,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="api-gateway"
        )
        
        await self.broker.publish(
            event=event.model_dump(),
            queue=user_events_queue,
            routing_key="user.login"
        )
        logger.info(f"Published user login event for: {email}")
        
        
events_publisher = ApiGatewayEventPublisher()
    
        
