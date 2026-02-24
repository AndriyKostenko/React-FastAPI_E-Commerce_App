from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitQueue
from pydantic import BaseModel

from shared.settings import Settings


class BaseEventPublisher:
    """Base Event publisher using FastStream (RabbitMQ)"""
    def __init__(self, broker: RabbitBroker, logger: Logger, settings: Settings) -> None:
        self.broker: RabbitBroker = broker
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

    # TODO: check for async compatibility (looks like correct)
    # and check if needed to be refactored using the decorator:
    # @broker.publisher(queue=RabbitQueue("user.events", durable=True))
    async def publish_an_event(self, message: BaseModel, queue: RabbitQueue):
        """Generic method to publish an event"""
        # the message will be automaticallyy converted to JSON by FastStream..(suppouse to be)
        await self.broker.publish(
            message=message.model_dump_json(),
            queue=queue,
        )
        self.logger.info(f"Published event with msg: {message.model_dump_json()} to: {queue}")
