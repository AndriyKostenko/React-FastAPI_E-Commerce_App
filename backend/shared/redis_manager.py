from typing import Any, AsyncGenerator, Callable, Optional
from functools import wraps
from time import perf_counter
from math import ceil
from logging import Logger

import orjson
from fastapi import Request, Response
from redis import asyncio as aioredis
from shared.base_exceptions import BaseAPIException, RateLimitExceededError
from shared.customized_json_response import JSONResponse





class RedisManager:
    """
    Unified Redis manager for caching and rate limiting across microservices.
    Provides decorators for both caching and rate limiting functionality (for endpoints) and cache / ratelimiting methods for api-gateway.
    """
    def __init__(self, service_prefix: str, redis_url: str, logger: Logger, service_api_version: str):
        self.logger: Logger = logger
        self.service_prefix: str = service_prefix
        self.redis_url: str = redis_url
        self._redis: aioredis.Redis | None = None
        self.http_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
        self.service_api_version: str = service_api_version
        self.namespaces: list[str] = ["users", "products", "categories", "orders", "reviews", "images"]
        
    # property to lazily initialize RedisCache
    @property
    def redis(self) -> aioredis.Redis:
        """Lazy-loaded Redis connection"""
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                    )
                self.logger.debug(f"Using Redis connection: {self._redis}")
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis connection: {str(e)}")
                raise RuntimeError(f"Failed to initialize Redis connection: {str(e)}")
        # This allows us to use self.redis to access the Redis instance
        return self._redis
    
    
    # ==================== CACHING FUNCTIONALITY ====================
    
    async def _async_gen_wrapper(self, data: list[bytes]) -> AsyncGenerator[bytes, None]:
        """
        Helper method to recreate body iterator
        """
        for chunk in data:
            yield chunk
    
    
    def _generate_cache_key(
        self,
        request: Request,
        pattern: str | None = None,
        force_method: str | None = None) -> str | None:
        """
        Generate cache key for a request or a namespace pattern.
        Includes:
            - service_prefix
            - HTTP method (optionally forced)
            - API version
            - path or pattern
            - normalized query parameters (for full requests)
        """
        # Validate force_method if provided
        if force_method is not None and force_method not in self.http_methods:
            self.logger.error(
                f"Invalid force_method provided: {force_method}. Must be one of: {self.http_methods}"
            )
            return None

        # Use forced method or request method
        method = force_method if force_method else str(request.method).upper()

        # Base path
        path = str(request.url.path)

        # Normalize query parameters in case they are added in different orders
        query_params = "&".join([f"{k}={v}" for k, v in sorted(request.query_params.items())])

        # Determine final path for cache key
        if pattern:
            # Ensure API version and pattern are concatenated properly
            versioned_path = f"{self.service_api_version.rstrip('/')}/{pattern.lstrip('/')}"
            cache_key = f"{self.service_prefix}:cache:{method}:{versioned_path}*"
        else:
            cache_key = f"{self.service_prefix}:cache:{method}:{path}:{query_params}"

        self.logger.debug(
            f"Generating cache key: {cache_key}, "
            f"Original URL: {request.url}, "
            f"Raw path: {path}, "
            f"Query params: {query_params}"
        )

        return cache_key


    async def clear_cache_namespace(
        self,
        request: Request,
        namespace: str,
        force_method: str | None = "GET") -> bool:
        """
        Clear all keys in a namespace (pattern-based) safely using Redis SCAN.
        Works with API versioning automatically.
        """
        if namespace not in self.namespaces:
            self.logger.error("Namespace is missing or incorrect for clearing cache.")
            return False

        # Generate pattern-based cache key including API version
        pattern_key = self._generate_cache_key(
            request=request,
            pattern=namespace,
            force_method=force_method
        )

        if not pattern_key:
            self.logger.error(f"Failed to generate cache key for namespace: {namespace}")
            return False

        deleted_count = 0
        try:
            # adding count
            async for key in self.redis.scan_iter(match=pattern_key, count=1000):
                await self.redis.delete(key)
                deleted_count += 1

            self.logger.info(f"Cleared: {deleted_count} keys in namespace: '{namespace}'")
            return True

        except Exception as e:
            self.logger.error(f"Error clearing namespace '{namespace}': {str(e)}", exc_info=True)
            return False

        
    def _should_skip_caching(self, request: Request, response: Response) -> bool:
        """
        Determining if response should be cached
        """
        # Defining paths that should never be cached
        not_monitoring_patterns = ["/health", "/metrics", "/status", "/ping", "/ready", "/live"]
        is_not_monitoring_endpoint = any(request.url.path.startswith(pattern) for pattern in not_monitoring_patterns)
        
        return (
            request.method != "GET" 
            or not (200 <= response.status_code < 300) 
            or response.headers.get("Cache-Control") == "no-cache"
            or is_not_monitoring_endpoint
        )
    
    
    async def cache_response(self, request: Request, response: Response, ttl: int = 300):
        """
        Cache a response for a given request.
        Includes API version in cache keys.
        Default TTL is 5 minutes.
        """
        if self._should_skip_caching(request, response):
            self.logger.warning(
                f"Skipping caching response for method: {request.method}, path: {request.url.path} "
                "because of method, status code, or headers"
            )
            return

        try:
            # Generate cache key including API version
            cache_key = self._generate_cache_key(request=request)
            if not cache_key:
                self.logger.error("Cannot generate cache key for caching response, skipping cache.")
                return

            status_code = response.status_code
            self.logger.debug(f"Caching response for key: {cache_key} with status code: {status_code} ...")

            response_body = None

            # 1. Regular JSONResponse
            if hasattr(response, "body") and response.body:
                response_body = response.body
            # 2. Custom response with content
            elif hasattr(response, "content") and response.content:
                response_body = response.content
            # 3. Streaming response
            elif hasattr(response, "body_iterator") and response.body_iterator:
                body_parts = []
                async for chunk in response.body_iterator:
                    body_parts.append(chunk)

                response_body = b"".join(body_parts)
                response.body_iterator = self._async_gen_wrapper(body_parts)
            else:
                self.logger.warning(f"Cannot access response body for caching: {cache_key}")
                return

            if not response_body:
                self.logger.warning(f"Response body is empty, skipping cache for: {cache_key}")
                return

            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8")

            try:
                content = orjson.loads(response_body)
            except orjson.JSONDecodeError as e:
                self.logger.warning(f"Response not JSON serializable, skipping cache for: {cache_key} - {str(e)}")
                return

            # Store in Redis with API version in key
            await self.set_response_for_caching(
                key=cache_key,
                seconds=ttl,
                value={"content": content, "status_code": status_code}
            )

            self.logger.debug(f"Successfully cached response for: {cache_key}")

        except Exception as e:
            self.logger.error(f"Error caching response: {str(e)}")
            return

            
    async def get_cached_response(self, request: Request) -> Optional[JSONResponse]:
        """
        Check if a response for this request is cached and return it.
        For use in API Gateway middleware.
        """
        if request.method != "GET" or "Authorization" in request.headers:
            self.logger.info(f"Skipping getting the cached response coz of non GET or Authorization in headers...")
            return None
        
        cache_key = self._generate_cache_key(request=request)
        cached_data = await self.redis.get(cache_key)
        
        if cached_data:
            cached_dict = orjson.loads(cached_data)
            self.logger.debug(f"Gateway returnes cached data for: {cache_key}")
            return JSONResponse(content=cached_dict["content"],
                                status_code=cached_dict["status_code"])
        
        self.logger.debug(f"No cached data for key: {cache_key}")
        return None
           
            
    async def set_response_for_caching(self, key: str, seconds: int, value: dict) -> None:
        """
        Set a response in Redis for caching.
        
        Args:
            key: Cache key
            seconds: Time to live in seconds
            value: Response data to cache
        """
        try:
            await self.redis.setex(
                name=key,
                time=seconds,
                value=orjson.dumps(value)
            )
            self.logger.debug(f"Set response for caching with key: {key}")
        except Exception as e:
            self.logger.error(f"Error setting response for caching: {str(e)}")
    
    
    def cached(self, ttl: int) -> Callable:
        """
        Decorator for caching endpoint responses with API version included in cache key.
        Only caches successful JSONResponse objects.
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                # Find the Request object from args or kwargs
                request: Request | None = next(
                    (arg for arg in list(kwargs.values()) + list(args) if isinstance(arg, Request)),
                    None
                )

                if not request:
                    self.logger.error(f"No Request object provided. Skipping cache for {func.__name__}")
                    return await func(*args, **kwargs)

                # Generate cache key including API version
                cache_key = self._generate_cache_key(request=request)
                if not cache_key:
                    self.logger.error(f"Cannot generate cache key. Skipping cache for {func.__name__}")
                    return await func(*args, **kwargs)

                try:
                    cached_data = await self.redis.get(cache_key)
                    if cached_data:
                        cached_dict = orjson.loads(cached_data)
                        self.logger.debug(f"Returning cached data for function {func.__name__}: {cached_dict['content']}")
                        return JSONResponse(
                            content=cached_dict["content"],
                            status_code=cached_dict["status_code"]
                        )

                    # Call the original function
                    response = await func(*args, **kwargs)

                    # Only cache JSONResponse with successful status codes
                    if isinstance(response, JSONResponse) and 200 <= response.status_code < 300:
                        response_body = None
                        if hasattr(response, "body") and response.body:
                            response_body = response.body
                        elif hasattr(response, "content") and response.content:
                            response_body = response.content
                        elif hasattr(response, "body_iterator") and response.body_iterator:
                            body_parts = []
                            async for chunk in response.body_iterator:
                                body_parts.append(chunk)
                            response_body = b"".join(body_parts)
                            response.body_iterator = self._async_gen_wrapper(body_parts)

                        if response_body:
                            if isinstance(response_body, bytes):
                                response_body = response_body.decode("utf-8")
                            try:
                                content = orjson.loads(response_body)
                                await self.set_response_for_caching(
                                    key=cache_key,
                                    seconds=ttl,
                                    value={"content": content, "status_code": response.status_code}
                                )
                                self.logger.debug(f"Cached response for function {func.__name__}: {cache_key}")
                            except orjson.JSONDecodeError:
                                self.logger.warning(f"Response not JSON serializable, skipping cache for {func.__name__}")
                    return response

                except BaseAPIException as e:
                    # Don't cache exceptions
                    self.logger.debug(f"Not caching error response: {str(e)}")
                    raise
                except Exception as e:
                    self.logger.error(f"Cache error in {func.__name__}: {str(e)}")
                    return await func(*args, **kwargs)

            return wrapper
        return decorator


    async def invalidate_cache(self, request: Request) -> bool:
        """
        Invalidate cache for a specific key in the given namespace.
        """
        if not request:
            self.logger.error(f"Request must be provided for cache invalidation.")
            return False
        # Construct the cache key
        cache_key = self._generate_cache_key(request=request)
        if not cache_key:
            self.logger.error(f"Cache key generation failed, skipping invalidation.")
            return False

        success = await self.redis.delete(cache_key)
        if success:
            self.logger.info(f"Invalidated cache for key: {cache_key}")
            return True
        else:
            self.logger.warning(f"Cache key not found for invalidation: {cache_key}")
            return False
        
    # ==================== RATE LIMITING FUNCTIONALITY ====================
    
    def ratelimiter(self, times: int , seconds: int ) -> Callable:
        """
        Decorator to apply rate limiting to a FastAPI route.
        
        Args:
            times: Maximum number of requests allowed in the time window
            seconds: Time window in seconds
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                # checking for request object passed to funtion (endpoint)
                request: Request | None = next((argument for argument in list(kwargs.values()) + list(args) if isinstance(argument, Request) ), None)
                if not request:
                    self.logger.warning(f'No request object for func.: {func.__name__} is provided for ratelimiting!')
                    return await func(*args, **kwargs)
                    
                await self.is_rate_limited(request, times, seconds)
                return await func(*args, **kwargs)
            return wrapper
        return decorator


    def _generate_rate_limit_key(self, request: Request) -> str:
        """Generate a unique rate limit key based on client IP and endpoint"""
        client_ip = request.client.host 
        endpoint = request.url.path
        return f"{self.service_prefix}:ratelimit:{client_ip}:{endpoint}"


    # by default max 100 calls to any proxy per 60 secs
    async def is_rate_limited(self, request: Request, times: int = 100, seconds: int = 60) -> bool | Exception:
        """Check if the rate limit is exceeded using sliding window"""
        try:
            self.logger.debug(f'Checking if endpoint: {request.url} is rate limited...')
            key = self._generate_rate_limit_key(request)
            pipe = self.redis.pipeline()
            now = perf_counter()
            
            # Add current request timestamp
            pipe.zadd(key, {str(now): now})
            # Remove old requests outside the window
            pipe.zremrangebyscore(key, 0, now - seconds)
            # Count requests in current window
            pipe.zcard(key)
            # Set key expiration
            pipe.expire(key, seconds)
            # Get oldest timestamp
            pipe.zrange(key, 0, 0)
            
            results = await pipe.execute()
            request_count = results[2]
            oldest = results[4]
            
            if request_count <= times:
                return False
            
            # Calculate retry_after
            if oldest:
                oldest_ts = float(oldest[0])
                retry_after = ceil((oldest_ts + seconds) - now)
                retry_after = max(retry_after, 1)
            else:
                retry_after = seconds
            
            self.logger.warning(f"Rate limit exceeded for: {key}")
            raise RateLimitExceededError(
                client_ip=request.client.host, # type: ignore
                retry_after=retry_after
            )
        except RateLimitExceededError:
        # Re-raise rate limit errors
            raise
            
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {str(e)}")
            # Allow request on Redis failure (fail-open approach)
            return False

    # ==================== CONNECTION MANAGEMENT ====================

    async def health_check(self) -> dict:
        """Comprehensive health check for Redis"""
        try:
            redis_client = await self.redis
            start_time = perf_counter()
            await redis_client.ping()
            response_time = perf_counter() - start_time
            
            info = await redis_client.info()
            self.logger.debug(f"Redis is healthy")
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
        except Exception as e:
            self.logger.error(f"Redis is not healthy")
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None
            }
    
    
    async def close(self) -> None:
        """Close the Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self.logger.info(f"Redis connection closed for {self.service_prefix}")
        



    
    




