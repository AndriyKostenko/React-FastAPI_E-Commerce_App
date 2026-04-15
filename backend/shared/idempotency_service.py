from logging import Logger
from uuid import UUID
from datetime import datetime, timezone

from orjson import dumps

from shared.redis_manager import RedisManager


class IdempotencyEventService(RedisManager):
    """Service to ensure idempotent processing of events using Redis"""
    def __init__(self,
                service_prefix: str,
                logger: Logger,
                redis_url: str,
                service_api_version: str,
                ttl_hours: int = 72,) -> None:
        super().__init__(service_prefix,
                         redis_url,
                         logger,
                         service_api_version)
        self.logger: Logger = logger
        self.ttl_seconds: int= ttl_hours * 3600 # Convert hours to seconds for Redis TTL
        self.prefix: str = service_prefix

    def _generate_event_cache_key(self, event_id: str | UUID, event_type: str) -> str:
        """Generating Redis key for event tracking"""
        return f"{self.prefix}:{event_type}:{str(event_id)}"

    async def try_claim_event(self, event_id: str | UUID, event_type: str) -> bool:
        """Atomically claim an event for processing using SET NX.

        Returns True if this worker successfully claimed the event (should process it).
        Returns False if another worker already claimed or processed it (skip).

        Uses a single atomic Redis SET NX to avoid the TOCTOU race condition
        that would arise from separate EXISTS + SET calls.
        """
        key = self._generate_event_cache_key(event_id, event_type)
        claimed = await self.redis.set(key, "processing", nx=True, ex=self.ttl_seconds)
        if claimed is None:
            self.logger.warning(f"Event {event_id} of type {event_type} already claimed/processed — skipping.")
            return False
        return True

    async def mark_event_as_processed(self,
                                      event_id: str | UUID,
                                      event_type: str,
                                      order_id: str | UUID | None,
                                      result: str) -> None:
        """Overwrite the provisional 'processing' marker with full metadata once done."""
        key = self._generate_event_cache_key(event_id, event_type)
        metadata = {
            "event_id": str(event_id),
            "event_type": event_type,
            "order_id": str(order_id) if order_id else None,
            "result": result,
            "processed_at": str(datetime.now(timezone.utc))
        }
        value = dumps(metadata).decode()
        await self.redis.set(key, value, ex=self.ttl_seconds)
        self.logger.debug(f"Marked event: {event_id} as processed !")
