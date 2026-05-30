from typing import Any, Optional
from functools import wraps

from orjson import loads, dumps, JSONDecodeError
from fastapi import Request
from shared.exceptions.base_exceptions import BaseAPIException
from shared.utils.customized_json_response import JSONResponse
from shared.managers.redis_base import RedisBase


class CacheManager(RedisBase):
    """
    Caching layer: key generation, read-through, write-through, namespace invalidation,
    and a @cached decorator for individual route handlers.
    """
    # Ordered most-specific → least-specific so the first match wins.
    # Values are lists to allow a single mutation to invalidate multiple namespaces.
    # e.g. updating a category also stales cached product-detail responses that embed category data.
    _INVALIDATION_NAMESPACE_MAP: list[tuple[str, list[str]]] = [
        ("products/detailed", ["products"]),
        ("/products", ["products"]),
        ("/categories", ["categories", "products"]),   # category change → stale embedded product data
        ("/images", ["images", "products"]),            # image change → stale embedded product data
        ("/reviews", ["reviews", "products"]),          # review change → stale embedded product data
        ("/orders", ["orders"]),
        ("/users", ["users"]),
        ("/notifications", ["notifications"]),
    ]

    _CACHE_TTL_MAP: list[tuple[str, int]] = [
        ("/products/detailed", 600),
        ("/products", 300),
        ("/categories", 300),
        ("/images", 300),
        ("/reviews", 300),
    ]

    DEFAULT_TTL: int = 300

    def __init__(self, service_api_version: str, **kwargs):
        super().__init__(**kwargs)
        self.service_api_version: str = service_api_version
        self.http_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
        self.namespaces: list[str] = [
            "users", "products", "categories", "orders",
            "reviews", "images", "notifications",
        ]

    # ---- key generation ----

    def _generate_cache_key(
        self,
        request: Request,
        pattern: str | None = None,
        force_method: str | None = None) -> str | None:
        """
        Generate cache key for a request or a namespace pattern.
        Includes service_prefix, HTTP method, API version, path, and sorted query params.
        """
        if force_method is not None and force_method not in self.http_methods:
            self.logger.error(
                f"Invalid force_method: {force_method}. Must be one of: {self.http_methods}"
            )
            return None

        method = force_method if force_method else str(request.method).upper()
        path = str(request.url.path)
        query_params = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))

        if pattern:
            versioned_path = f"{self.service_api_version.rstrip('/')}/{pattern.lstrip('/')}"
            cache_key = f"{self.service_prefix}:cache:{method}:{versioned_path}*"
        else:
            cache_key = f"{self.service_prefix}:cache:{method}:{path}:{query_params}"

        self.logger.debug(
            f"Generated cache key: {cache_key}, URL: {request.url}, "
            f"path: {path}, query: {query_params}"
        )
        return cache_key

    # ---- namespace invalidation ----

    async def clear_cache_namespace(
        self,
        request: Request,
        namespace: str,
        force_method: str | None = "GET") -> None:
        """Clear all keys in a namespace using Redis SCAN (requires an HTTP Request)."""
        if namespace not in self.namespaces:
            self.logger.error("Namespace is missing or incorrect for clearing cache.")
            return

        pattern_key = self._generate_cache_key(
            request=request,
            pattern=namespace,
            force_method=force_method,
        )
        if not pattern_key:
            self.logger.error(f"Failed to generate cache key for namespace: {namespace}")
            return

        deleted_count = 0
        try:
            async for key in self.redis.scan_iter(match=pattern_key, count=1000):
                await self.redis.delete(key)
                deleted_count += 1
            self.logger.info(f"Cleared {deleted_count} keys in namespace: '{namespace}'")
        except Exception as e:
            self.logger.error(f"Error clearing namespace '{namespace}': {str(e)}", exc_info=True)

    async def invalidate_namespace(self, namespace: str, method: str = "GET") -> None:
        """
        Clear all cached keys for a namespace without requiring an HTTP Request.
        Intended for background consumers (e.g. FastStream) that mutate data.

        Key pattern: {service_prefix}:cache:{method}:{api_version}/{namespace}*
        """
        if namespace not in self.namespaces:
            self.logger.error(f"Unknown namespace '{namespace}' — skipping cache invalidation.")
            return

        versioned_path = f"{self.service_api_version.rstrip('/')}/{namespace.lstrip('/')}"
        pattern_key = f"{self.service_prefix}:cache:{method}:{versioned_path}*"

        deleted_count = 0
        try:
            async for key in self.redis.scan_iter(match=pattern_key, count=1000):
                await self.redis.delete(key)
                deleted_count += 1
            self.logger.info(f"Invalidated {deleted_count} keys in namespace: '{namespace}'")
        except Exception as e:
            self.logger.error(f"Error invalidating namespace '{namespace}': {str(e)}", exc_info=True)

    # ---- response caching ----

    async def cache_response(self, request: Request, body: bytes, status_code: int, ttl: int = 300) -> None:
        """
        Cache a response body for a given request.
        Accepts pre-read body bytes (required because call_next() returns a streaming
        response whose body_iterator must be consumed at the middleware level).
        Default TTL is 5 minutes.
        """
        monitoring_patterns = ["/health", "/metrics", "/status", "/ping", "/ready", "/live"]
        if any(request.url.path.startswith(p) for p in monitoring_patterns):
            return

        if request.method != "GET" or not (200 <= status_code < 300):
            self.logger.debug(
                f"Skipping cache: method={request.method}, status={status_code}, "
                f"path={request.url.path}"
            )
            return

        try:
            cache_key = self._generate_cache_key(request=request)
            if not cache_key:
                self.logger.error("Cannot generate cache key for caching response, skipping.")
                return

            if not body:
                self.logger.warning(f"Response body is empty, skipping cache for: {cache_key}")
                return

            response_body = body.decode("utf-8") if isinstance(body, bytes) else body

            try:
                content = loads(response_body)
            except JSONDecodeError as e:
                self.logger.warning(f"Response not JSON serializable, skipping cache: {cache_key} — {e}")
                return

            await self.set_response_for_caching(
                key=cache_key,
                seconds=ttl,
                value={"content": content, "status_code": status_code},
            )
            self.logger.debug(f"Cached response for: {cache_key}")
        except Exception as e:
            self.logger.error(f"Error caching response: {str(e)}")

    async def get_cached_response(self, request: Request, is_public: bool = False) -> Optional[JSONResponse]:
        """
        Return a cached response if available, or None.

        For protected endpoints: skips cache when auth credentials are present
        (Authorization header or access_token cookie) to avoid cross-user data leaks.
        For public endpoints: serves from cache regardless of auth headers.
        """
        if request.method != "GET":
            self.logger.info("Skipping cache lookup: non-GET request.")
            return None

        if not is_public:
            is_authenticated = (
                "Authorization" in request.headers
                or request.cookies.get("access_token") is not None
            )
            if is_authenticated:
                self.logger.info("Skipping cache lookup: authenticated request to protected endpoint.")
                return None

        cache_key = self._generate_cache_key(request=request)
        if not cache_key:
            self.logger.error("Cannot generate cache key, skipping cache retrieval.")
            return None

        cached_data: bytes | None = await self.redis.get(cache_key)
        if cached_data:
            cached_dict = loads(cached_data)
            self.logger.debug(f"Cache hit for: {cache_key}")
            return JSONResponse(
                content=cached_dict["content"],
                status_code=cached_dict["status_code"],
            )

        self.logger.debug(f"Cache miss for: {cache_key}")
        return None

    async def set_response_for_caching(self, key: str, seconds: int, value: dict[str, Any]) -> None:
        """Set a response in Redis with a TTL."""
        try:
            await self.redis.setex(name=key, time=seconds, value=dumps(value))
            self.logger.debug(f"Set cache key: {key}")
        except Exception as e:
            self.logger.error(f"Error setting cache: {str(e)}")

    async def invalidate_cache(self, request: Request) -> bool:
        """Invalidate the cache entry for a specific request's key."""
        if not request:
            self.logger.error("Request must be provided for cache invalidation.")
            return False
        cache_key = self._generate_cache_key(request=request)
        if not cache_key:
            self.logger.error("Cache key generation failed, skipping invalidation.")
            return False
        success = await self.redis.delete(cache_key)
        if success:
            self.logger.info(f"Invalidated cache key: {cache_key}")
            return True
        self.logger.warning(f"Cache key not found for invalidation: {cache_key}")
        return False

    # ---- @cached decorator ----

    def cached(self, ttl: int):
        """
        Decorator for caching endpoint responses.
        Only caches successful JSONResponse objects.
        Note: has no effect when gateway_middleware also caches the same key.
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                request: Request | None = next(
                    (arg for arg in list(kwargs.values()) + list(args) if isinstance(arg, Request)),
                    None,
                )
                if not request:
                    self.logger.error(f"No Request object. Skipping cache for: {func.__name__}")
                    return await func(*args, **kwargs)

                cache_key = self._generate_cache_key(request=request)
                if not cache_key:
                    self.logger.error(f"Cannot generate cache key. Skipping cache for {func.__name__}")
                    return await func(*args, **kwargs)

                try:
                    cached_data = await self.redis.get(cache_key)
                    if cached_data:
                        cached_dict = loads(cached_data)
                        self.logger.debug(f"Cache hit in {func.__name__}: {cache_key}")
                        return JSONResponse(
                            content=cached_dict["content"],
                            status_code=cached_dict["status_code"],
                        )

                    response = await func(*args, **kwargs)

                    if isinstance(response, JSONResponse) and 200 <= response.status_code < 300:
                        response_body = getattr(response, "body", None)
                        if response_body:
                            body_str = response_body.decode("utf-8") if isinstance(response_body, bytes) else response_body
                            try:
                                content = loads(body_str)
                                await self.set_response_for_caching(
                                    key=cache_key,
                                    seconds=ttl,
                                    value={"content": content, "status_code": response.status_code},
                                )
                                self.logger.debug(f"Cached via decorator in {func.__name__}: {cache_key}")
                            except JSONDecodeError:
                                self.logger.warning(f"Response not JSON serializable in {func.__name__}")
                    return response

                except BaseAPIException:
                    raise
                except Exception as e:
                    self.logger.error(f"Cache error in {func.__name__}: {str(e)}")
                    return await func(*args, **kwargs)

            return wrapper
        return decorator


    def get_invalidation_namespaces(self, path: str) -> list[str]:
        """Return all cache namespaces to invalidate after a successful mutation on *path*."""
        path_lower = path.lower()
        for segment, namespaces in self._INVALIDATION_NAMESPACE_MAP:
            if segment in path_lower:
                return namespaces
        return []

    def get_cache_ttl(self, path: str) -> int:
        """Return the TTL (seconds) to use when caching a GET response for *path*."""
        path_lower = path.lower()
        for segment, ttl in self._CACHE_TTL_MAP:
            if segment in path_lower:
                return ttl
        return self.DEFAULT_TTL