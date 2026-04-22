from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitExchange
from pydantic import BaseModel

from shared.settings import Settings


class BaseEventPublisher:
    """Base Event publisher using FastStream (RabbitMQ)"""
    def __init__(self, rabbitmq_broker: RabbitBroker, logger: Logger, settings: Settings) -> None:
        self.broker: RabbitBroker = rabbitmq_broker
        self._is_started: bool = False
        self.logger: Logger = logger

    async def start(self):
        """Start the broker connection"""
        if not self._is_started:
            await self.broker.start()
            self._is_started = True
            self.logger.info("Base Event publisher started")

    async def stop(self):
        """Stop the broker connection"""
        if self._is_started:
            await self.broker.stop()
            self._is_started = False
            self.logger.info("Base Event event publisher stopped")

    async def publish_an_event(self, event: BaseModel, exchange: RabbitExchange, routing_key: str) -> None:
        """Publish an event to a TOPIC exchange with the given routing key.

        FastStream serialises BaseModel to JSON and sets content_type='application/json'
        automatically. persist=True ensures messages survive a broker restart.
        The exchange routes the message to bound queues whose binding key matches
        the routing_key pattern.
        """
        await self.broker.publish(
            message=event,
            exchange=exchange,
            routing_key=routing_key,
            persist=True,
        )
        self.logger.info(f"Published '{routing_key}' to exchange '{exchange.name}': {event.model_dump_json()}")
