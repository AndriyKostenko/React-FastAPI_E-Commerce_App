from logging import Logger
from uuid import UUID
from datetime import datetime, timezone

from orjson import dumps

from shared.redis_manager import RedisManager



class IdempotencyEventService(RedisManager):
    """Service to ensure idempotent proctssing of events using Redis"""
    def __init__(self,
                service_prefix: str,
                logger: Logger,
                redis_url: str,
                service_api_version: str,
                ttl_hours: int = 24,) -> None:
        super().__init__(service_prefix,
                         redis_url,
                         logger,
                         service_api_version)
        self.logger: Logger = logger
        self.ttl_seconds: int= ttl_hours * 3600
        self.prefix: str = service_prefix

    def _generate_event_cache_key(self, event_id: UUID, event_type: str) -> str:
        """Generating Redis key for event tracking"""
        return f"{self.prefix}:{event_type}:{str(event_id)}"

    async def is_event_processed(self, event_id: UUID, event_type: str) -> bool:
        """Checking if event been processed"""
        key = self._generate_event_cache_key(event_id, event_type)
        exists = await self.redis.exists(key)
        if exists:
            self.logger.warning(f"Event: {event_id} of type: {event_type} was already processesd. Skipping duplicate processing")
            return True
        return False

    async def mark_event_as_processed(self,
                                      event_id: UUID,
                                      event_type: str,
                                      order_id: UUID,
                                      result: str) -> None:
        """Mark event as processed with metadata"""
        key = self._generate_event_cache_key(event_id, event_type)
        metadata = {
            "event_id": str(event_id),
            "event_type": event_type,
            "order_id": str(order_id),
            "result": result,
            "processed_at": str(datetime.now(timezone.utc))
        }
        value = dumps(metadata).decode()
        await self.redis.set(key, value, ex=self.ttl_seconds)
        self.logger.debug(f"Marked event: {event_id} as processed !")
