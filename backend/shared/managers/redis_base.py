from typing import Any
from time import perf_counter
from logging import Logger

from redis import asyncio as aioredis


class RedisBase:
    """
    Minimal Redis base: manages the connection lifecycle only.
    Subclass this when you only need raw Redis access (no cache/rate-limit logic).
    """

    def __init__(self, service_prefix: str, redis_url: str, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.service_prefix: str = service_prefix
        self.redis_url: str = redis_url
        self.logger: Logger = logger
        self._redis: aioredis.Redis | None = None

    @property
    def redis(self) -> aioredis.Redis:
        """Lazy-loaded Redis connection."""
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                self.logger.debug(f"Using Redis connection: {self._redis}")
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis connection: {str(e)}")
                raise RuntimeError(f"Failed to initialize Redis connection: {str(e)}")
        return self._redis

    async def connect(self) -> None:
        """
        Establish and verify the Redis connection at service startup.
        Raises RuntimeError if Redis is unreachable — aborts startup intentionally.
        """
        try:
            await self.redis.ping()
            self.logger.info(f"Redis connection established for {self.service_prefix}")
        except Exception as error:
            self.logger.error(f"Redis connection failed for {self.service_prefix}: {str(error)}")
            raise RuntimeError(f"Redis unavailable for {self.service_prefix}: {str(error)}")

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive health check for Redis."""
        try:
            start_time = perf_counter()
            await self.redis.ping()
            response_time = perf_counter() - start_time
            info = await self.redis.info()
            self.logger.debug("Redis is healthy")
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown"),
            }
        except Exception as e:
            self.logger.error("Redis is not healthy")
            return {"status": "unhealthy", "error": str(e), "response_time_ms": None}

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self.logger.info(f"Redis connection closed for {self.service_prefix}")
