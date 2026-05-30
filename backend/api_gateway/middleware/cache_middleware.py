from typing import Any

from fastapi import Request, Response

from shared.managers.cache_manager import CacheManager
from shared.managers.ratelimit_manager import RateLimitManager


class GatewayRequestMiddleware:
    """
    Class-based middleware that encapsulates the full gateway request pipeline:
    global rate limiting, cache read-through / write-through, and cache invalidation.

    Holds a CacheManager for response caching/invalidation and a RateLimitManager
    for global IP-based throttling.
    """

    # Global rate-limit defaults applied to every request.
    _RATE_LIMIT_TIMES: int = 10_000
    _RATE_LIMIT_SECONDS: int = 60

    def __init__(self, cache_manager: CacheManager, rate_limit_manager: RateLimitManager) -> None:
        self.cache_manager: CacheManager = cache_manager
        self.rate_limit_manager: RateLimitManager = rate_limit_manager

    async def __call__(self, request: Request, call_next: Any, is_public: bool) -> Response:
        """
        Execute the full gateway middleware pipeline for a single request.

        Steps:
          1. Global rate-limit check (fails-open on Redis errors).
          2. Return cached GET response when available.
          3. Forward request to the downstream microservice.
          4. On 2xx GET: buffer body, cache it, reconstruct a streamable Response.
          5. On 2xx mutation: invalidate stale cache namespaces.

        Args:
            request:          Incoming FastAPI/Starlette request.
            call_next:        Middleware callable to forward to the next layer.
            is_public:        True when the endpoint is caller-invariant
                              (same response for all users).
        """
        # 1. Global rate limit: fail-open so Redis outages don't block all traffic.
        await self.rate_limit_manager.is_rate_limited(
            request,
            times=self._RATE_LIMIT_TIMES,
            seconds=self._RATE_LIMIT_SECONDS,
        )

        # 2. Return from cache if available.
        cached = await self.cache_manager.get_cached_response(request, is_public=is_public)
        if cached:
            return cached

        # 3. Determine cache-write eligibility before forwarding.
        #    Cache only when the response is identical for the caller:
        #    - public endpoints: always (caller-invariant by definition)
        #    - protected endpoints: only unauthenticated GETs (auth requests may carry user-specific data)
        is_authenticated = (
            "Authorization" in request.headers
            or request.cookies.get("access_token") is not None
        )
        should_cache = request.method == "GET" and (is_public or not is_authenticated)

        # 4. Forward to downstream microservice.
        response: Response = await call_next(request)

        # 5. Post-response cache handling.
        if 200 <= response.status_code < 300:
            if should_cache:
                # Consume the streaming body iterator (can only be read once).
                body = b"".join([chunk async for chunk in response.body_iterator])
                ttl = self.cache_manager.get_cache_ttl(request.url.path)
                await self.cache_manager.cache_response(request, body, response.status_code, ttl=ttl)
                # Reconstruct a plain Response since body_iterator is now exhausted.
                response = Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                    background=response.background,
                )
            elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
                namespaces = self.cache_manager.get_invalidation_namespaces(request.url.path)
                for namespace in namespaces:
                    await self.cache_manager.invalidate_namespace(namespace)

        return response

