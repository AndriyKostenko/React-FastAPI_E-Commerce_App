import time
from logging import Logger
from uuid import UUID

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

    def _owner_key(self, job_id: str) -> str:
        return f"{self._cache_manager.service_prefix}:image-job-owner:{job_id}"

    async def create(self, job_id: str, owner_id: UUID) -> None:
        """
        Persist a new job in *pending* state and record who submitted it.

        The owner lives under its own key because ``set_state`` rewrites the
        job document without reading it first, which would drop the field.
        """
        job_data = {"status": "pending", "submitted_at": time.time()}
        pipe = self._cache_manager.redis.pipeline()
        pipe.setex(name=self._key(job_id), time=self._JOB_TTL, value=orjson_dumps(job_data))
        pipe.setex(name=self._owner_key(job_id), time=self._JOB_TTL, value=str(owner_id))
        await pipe.execute()

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

    async def get_owner(self, job_id: str) -> UUID | None:
        """Who submitted the job, or None once the job has expired."""
        owner = await self._cache_manager.redis.get(self._owner_key(job_id))
        return UUID(_as_text(owner)) if owner else None

    async def get(self, job_id: str, owner_id: UUID) -> dict:
        """
        Return the job dict, or raise ImageGenerationJobNotFoundError.

        A job that belongs to someone else is reported as missing, so a caller
        cannot learn that another user's job id exists.
        """
        owner = await self._cache_manager.redis.get(self._owner_key(job_id))
        if owner is None or _as_text(owner) != str(owner_id):
            raise ImageGenerationJobNotFoundError()
        raw = await self._cache_manager.redis.get(self._key(job_id))
        if not raw:
            raise ImageGenerationJobNotFoundError()
        return orjson_loads(raw)


def _as_text(value: bytes | str) -> str:
    """Redis returns bytes unless the client decodes responses."""
    return value.decode() if isinstance(value, bytes) else value
