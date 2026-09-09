from typing import Any
from collections.abc import Sequence
from functools import wraps
from time import time
from math import ceil
from uuid import uuid4

from fastapi import Request

from shared.exceptions.base_exceptions import RateLimitExceededError
from shared.managers.redis_base import RedisBase
from shared.utils.client_ip import ClientIPResolver


class RateLimitManager(RedisBase):
    """Rate limiting layer: sliding-window rate limiter and @ratelimiter decorator."""

    def __init__(self, *args: Any, trusted_proxy_networks: Sequence[str] = (), **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._client_ip_resolver = ClientIPResolver(trusted_proxy_networks)

    def _get_client_ip(self, request: Request) -> str:
        """Resolve the client IP, honouring forwarding headers only from proxies."""
        return self._client_ip_resolver.resolve(request)

    @staticmethod
    def _authenticated_subject(request: Request) -> str | None:
        """The signed-in user this request belongs to, if any.

        Read from the validated token the auth middleware already put on the
        request, never from a header, so a caller cannot pick their own bucket.
        """
        current_user = getattr(request.state, "current_user", None)
        if current_user is None:
            return None
        user_id = getattr(current_user, "id", None)
        return f"user:{user_id}" if user_id else None

    def _generate_rate_limit_key(self, request: Request, identifier: str | None = None) -> str:
        """Build the bucket this request counts against.

        A signed-in user is counted per account rather than per address. Keying
        solely on IP means everyone behind one corporate NAT, campus network or
        mobile carrier gateway shares a bucket, so ordinary users throttle each
        other; it also lets one account spread abuse across addresses. Falling
        back to the resolved IP still covers anonymous traffic, which is where
        registration and login abuse actually comes from.
        """
        endpoint = request.url.path
        subject = self._authenticated_subject(request) or self._get_client_ip(request)
        if identifier:
            return f"{self.service_prefix}:ratelimit:{subject}:{identifier}:{endpoint}"
        return f"{self.service_prefix}:ratelimit:{subject}:{endpoint}"

    async def is_rate_limited(self, request: Request, times: int = 100, seconds: int = 60, identifier: str | None = None) -> bool:
        """Check if the rate limit is exceeded using a sliding window."""
        try:
            self.logger.debug(f"Checking rate limit for: {request.url}")
            key = self._generate_rate_limit_key(request, identifier=identifier)
            pipe = self.redis.pipeline()
            # Wall-clock, not perf_counter(): the window is shared by every
            # gunicorn worker and replica, and perf_counter()'s reference point
            # is process-local, so its scores are not comparable across them.
            now = time()
            # A unique member per request — two calls landing on the same
            # timestamp would otherwise collide and count as one.
            member = f"{now}:{uuid4().hex}"

            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(key, 0, now - seconds)
            pipe.zcard(key)
            pipe.expire(key, seconds)
            pipe.zrange(key, 0, 0, withscores=True)

            results = await pipe.execute()
            request_count = results[2]
            oldest = results[4]

            if request_count <= times:
                return False

            # Rejected requests must not count towards the window; leaving them
            # in would let a client hammering the endpoint keep pushing its own
            # window forward and stay locked out well past `seconds`.
            await self.redis.zrem(key, member)

            if oldest:
                oldest_ts = float(oldest[0][1])
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
