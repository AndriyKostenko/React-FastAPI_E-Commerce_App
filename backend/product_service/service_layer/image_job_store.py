import time
from logging import Logger

from orjson import loads as orjson_loads, dumps as orjson_dumps

from shared.managers.cache_manager import CacheManager
from exceptions.image_generation_exceptions import ImageGenerationJobNotFoundError


class ImageJobStore:
    """
    Manages image-generation job state in Redis.

    Each job is a compact JSON document stored under a namespaced TTL key.
    Write operations bypass the read-then-write pattern to eliminate
    unnecessary GET round-trips on the hot path.
    """

    _JOB_TTL: int = 3600  # 1 hour

    def __init__(self, cache_manager: CacheManager, logger: Logger) -> None:
        self._cache_manager = cache_manager
        self._logger = logger

    def _key(self, job_id: str) -> str:
        return f"{self._cache_manager.service_prefix}:image-job:{job_id}"

    async def create(self, job_id: str) -> None:
        """Persist a new job in *pending* state."""
        job_data = {"status": "pending", "submitted_at": time.time()}
        await self._cache_manager.redis.setex(
            name=self._key(job_id),
            time=self._JOB_TTL,
            value=orjson_dumps(job_data),
        )

    async def set_state(self, job_id: str, status: str, extra: dict | None = None) -> None:
        """Overwrite job state without a prior read (write-only optimisation)."""
        data: dict = {"status": status, "updated_at": time.time()}
        if extra:
            data.update(extra)
        await self._cache_manager.redis.setex(
            name=self._key(job_id),
            time=self._JOB_TTL,
            value=orjson_dumps(data),
        )

    async def get(self, job_id: str) -> dict:
        """Return the job dict or raise ImageGenerationJobNotFoundError."""
        raw = await self._cache_manager.redis.get(self._key(job_id))
        if not raw:
            raise ImageGenerationJobNotFoundError()
        return orjson_loads(raw)
