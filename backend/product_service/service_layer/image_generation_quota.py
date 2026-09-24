from logging import Logger
from uuid import UUID

from shared.settings import Settings
from shared.managers.cache_manager import CacheManager
from exceptions.image_generation_exceptions import ImageGenerationLimitExceededError


class GenerationQuotaService:
    """
    Enforces the per-user image-generation limit via Redis.

    Uses atomic INCR + conditional EXPIRE so the sliding window is initialised
    exactly once without a read-modify-write race condition.
    """

    def __init__(self, cache_manager: CacheManager, settings: Settings, logger: Logger) -> None:
        self._cache_manager = cache_manager
        self._settings = settings
        self._logger = logger

    def _quota_key(self, user_id: UUID) -> str:
        return f"{self._cache_manager.service_prefix}:image-generation:user:{user_id}"

    async def consume(self, user_id: UUID) -> int:
        """
        Atomically increment the user's usage counter and enforce the limit.

        Returns:
            Remaining quota (≥ 0) after this successful call.
        Raises:
            ImageGenerationLimitExceededError: when the limit has been reached.
        """
        limit = self._settings.PRODUCT_IMAGE_GENERATION_LIMIT
        window_seconds = self._settings.PRODUCT_IMAGE_GENERATION_WINDOW_HOURS * 3600
        key = self._quota_key(user_id)

        current_count = await self._cache_manager.redis.incr(key)
        if current_count == 1:
            await self._cache_manager.redis.expire(key, window_seconds)
        else:
            ttl = await self._cache_manager.redis.ttl(key)
            if ttl == -1:
                await self._cache_manager.redis.expire(key, window_seconds)

        ttl = await self._cache_manager.redis.ttl(key)
        retry_after = max(ttl, 1)

        if current_count > limit:
            raise ImageGenerationLimitExceededError(retry_after=retry_after, limit=limit)

        return max(limit - current_count, 0)
