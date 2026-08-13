from typing import Any
from functools import wraps
from time import perf_counter
from math import ceil

from fastapi import Request

from shared.exceptions.base_exceptions import RateLimitExceededError
from shared.managers.redis_base import RedisBase


class RateLimitManager(RedisBase):
    """Rate limiting layer: sliding-window rate limiter and @ratelimiter decorator."""

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, safely handling proxies if configured."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # First IP in X-Forwarded-For is client IP
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _generate_rate_limit_key(self, request: Request, identifier: str | None = None) -> str:
        """Generate a unique rate limit key based on client IP/identifier and endpoint."""
        client_ip = self._get_client_ip(request)
        endpoint = request.url.path
        if identifier:
            return f"{self.service_prefix}:ratelimit:{client_ip}:{identifier}:{endpoint}"
        return f"{self.service_prefix}:ratelimit:{client_ip}:{endpoint}"

    async def is_rate_limited(self, request: Request, times: int = 100, seconds: int = 60, identifier: str | None = None) -> bool:
        """Check if the rate limit is exceeded using a sliding window."""
        try:
            self.logger.debug(f"Checking rate limit for: {request.url}")
            key = self._generate_rate_limit_key(request, identifier=identifier)
            pipe = self.redis.pipeline()
            now = perf_counter()

            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, now - seconds)
            pipe.zcard(key)
            pipe.expire(key, seconds)
            pipe.zrange(key, 0, 0)

            results = await pipe.execute()
            request_count = results[2]
            oldest = results[4]

            if request_count <= times:
                return False

            if oldest:
                oldest_ts = float(oldest[0])
                retry_after = max(ceil((oldest_ts + seconds) - now), 1)
            else:
                retry_after = seconds

            self.logger.warning(f"Rate limit exceeded for: {key}")
            client_ip = self._get_client_ip(request)
            raise RateLimitExceededError(client_ip=client_ip, retry_after=retry_after)

        except RateLimitExceededError:
            raise
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {str(e)}")
            return False  # fail-open

    def ratelimiter(self, times: int, seconds: int, identifier_param: str | None = None):
        """
        Decorator to apply rate limiting to a FastAPI route.

        Args:
            times: Maximum number of requests allowed in the time window.
            seconds: Time window in seconds.
            identifier_param: Optional parameter name from kwargs to use as extra identifier.
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                request: Request | None = next(
                    (arg for arg in list(kwargs.values()) + list(args) if isinstance(arg, Request)),
                    None,
                )
                if not request:
                    self.logger.warning(f"No Request object for {func.__name__} — skipping rate limit.")
                    return await func(*args, **kwargs)
                identifier = None
                if identifier_param and identifier_param in kwargs:
                    value = kwargs[identifier_param]
                    # Request-body models and OAuth forms expose the address under
                    # different names.  Keying by it adds a per-account limit.
                    identifier = getattr(value, "email", None) or getattr(value, "username", None)
                    identifier = str(identifier or value)
                await self.is_rate_limited(request, times, seconds, identifier=identifier)
                return await func(*args, **kwargs)
            return wrapper
        return decorator
