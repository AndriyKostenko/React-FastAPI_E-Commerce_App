from typing import Any, AsyncGenerator, Callable, Optional
from functools import wraps
from time import perf_counter
from math import ceil

import orjson
from fastapi import Request
from redis import asyncio as aioredis
from shared.logger_config import setup_logger
from shared.base_exceptions import BaseAPIException, RateLimitExceededError
from shared.customized_json_response import JSONResponse





class RedisManager:
    """
    Unified Redis manager for caching and rate limiting across microservices.
    Provides decorators for both caching and rate limiting functionality (for endpoints) and cache / ratelimiting methods for api-gateway.
    """
    def __init__(self, service_prefix: str, redis_url: str):
        self.logger = setup_logger(__name__)
        self.service_prefix = service_prefix
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

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
    
    
    def _generate_cache_key(self, request: Request) -> str:
        #For API Gateway, cache based on endpoint and query params
        endpoint = request.url.path
        query_params = str(request.query_params) if request.query_params else ""
        return f"{self.service_prefix}:cache:{endpoint}:{query_params}"
        
        
    def _should_skip_caching(self, request: Request, response) -> bool:
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
            or "Authorization" in request.headers
            or is_not_monitoring_endpoint
        )
    
    async def cache_response(self, request: Request, response, ttl: int = 300):
        """
        Cache a response for a given request.
        For usage in API Gateway middleware
        default caching for each api-gateway proxy is 5 mins
        """
        
        if self._should_skip_caching(request, response):
            self.logger.warning(f"Skipping caching response for method: {request.method}, path: {request.url.path} coz of non applicable: method | path | status code | headers")
            return
            
        
        try:
            cache_key = self._generate_cache_key(request)
            status_code = response.status_code
            self.logger.debug(f"Caching response for key: {cache_key} with status code: {status_code} ...")
            
            response_body = None
            
            # 1. Regular JSONResponse
            if hasattr(response, "body") and response.body:
                response_body = response.body
                self.logger.debug(f"Found response.body: {len(response_body)} bytes")
            
            # 2. Custom response with content
            elif hasattr(response, "content") and response.content:
                response_body = response.content
                self.logger.debug(f"Found response.content: {len(response_body)} bytes")
                
            # TODO: not clear do i need to save a streaming responses...   
            # 3. Streaming response
            elif hasattr(response, "body_iterator") and response.body_iterator:
                self.logger.debug("Found streaming response, consuming iterator...")
                try:
                    body_parts = []
                    async for chunk in response.body_iterator:
                        body_parts.append(chunk)
                        
                    response_body = b"".join(body_parts)
                    self.logger.debug(f"Consumed streaming response: {len(response_body)} bytes")
                    
                    # Important: Recreate the body_iterator for the actual response
                    response.body_iterator = self._async_gen_wrapper(body_parts)
                    
                except Exception as e:
                    self.logger.warning(f"Cannot consume streaming response: {str(e)})")
                    return 
                
            else:
                self.logger.warning(f"Cannot access response body for caching: {cache_key}")
                
            #4. Ensure we have content to cache
            if not response_body:
                self.logger.warning(f"Response body is empty, skipping cache for: {cache_key}")
                return
            
            # 5. converting to bytes if needed
            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8")
                
            # 6. Attempting to cache JSON response
            try:
                content = orjson.loads(response_body)
            except orjson.JSONDecodeError as e:
                self.logger.warning(f"Response not JSON serializable, skipping cache for: {cache_key} - {str(e)}")
                return
            
            # 7. Saving to Redis
            await self.set_response_for_caching(
                key=cache_key,
                seconds=ttl,
                value={"content": content, "status_code": status_code}
            )
            self.logger.debug(f"Successfully cached response for: {cache_key}")
            
        except Exception as e:
            self.logger.error(f"Error caching response: {str(e)}")

            
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
        Decorator for caching endpoint responses.
        Route returns JSONResponse(content= status_code=201) → Cache stores {"content": data, "status_code": 201}  
        Route raises HTTPException(404) → Not cached → API Gateway receives 404
        
        Args:
            namespace: Cache namespace (e.g., 'users')
            key: Parameter name to use as cache key
            ttl: Time to live in seconds
            
        
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                # checking for request object passed to funtion (endpoint)
                request: Request | None = next((argument for argument in list(kwargs.values()) + list(args) if isinstance(argument, Request) ), None)
                
                if not ttl or not request:
                    self.logger.error(f"No ttl / request  is provided. Cache error for function: {func.__name__}. Skipping cache.")
                    return await func(*args, **kwargs)
                
                cache_key = self._generate_cache_key(request=request)
                
                try:
                    cached_data = await self.redis.get(cache_key)
                    
                    if cached_data:
                        cached_dict = orjson.loads(cached_data)
                        self.logger.debug(f"Returning cached data for function ({func.__name__}): {cached_dict["content"]}")
                        return JSONResponse(
                            content=cached_dict["content"],
                            status_code=cached_dict["status_code"]
                        )
                        
                    # Getting the fresh data
                    response = await func(*args, **kwargs)
                                           
                    # Handle custom JSONResponse object
                    if isinstance(response, JSONResponse):
                        status_code = response.status_code
                        # Only cache successful responses
                        if 200 <= status_code < 300:
                            if response.body:
                                try:
                                    body_content = orjson.loads(response.body)
                                    to_cache = {"content": body_content, "status_code": status_code}
                                    self.logger.debug(f"Content for caching: {to_cache}")
                                    await self.set_response_for_caching(
                                            key=cache_key,
                                            seconds=ttl,
                                            value=to_cache
                                        )
                                except orjson.JSONDecodeError as e:
                                    self.logger.warning(f"Response not JSON (orjson) serializable, skipping cache for: {cache_key} - {str(e)}")
                                    return response
                            return response
                    else:
                        self.logger.warning(f"Unexpected response type: {type(response)} for endpoint: {func.__name__}")
                        # If response is not JSONResponse, just return it
                        return response
  
                
                # The except BaseAPIException block will catch all non-success responses and prevent them from being cached.
                # monitoring only base exception for all custom errors coz all of them inhereted from it 
                except BaseAPIException as e:
                    self.logger.debug(f"Not caching error reponse: {str(e)}")
                    # not chaching and re-rasing an error
                    raise
                
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Cache error in {func.__name__}: {str(e)}")
                    # Return original function result on cache errors
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

        success = await self.redis.delete(cache_key)
        if success:
            self.logger.info(f"Invalidated cache for key: {cache_key}")
            return True
        else:
            self.logger.warning(f"Cache key not found for invalidation: {cache_key}")
            return False
        
        
    async def clear_cache_namespace(self, namespace: str) -> bool:
        """
        Clear all keys in a namespace (using Redis SCAN for safety with large datasets)
        """
        if not namespace:
            self.logger.error("Namespace must be provided for clearing cache.")
            return False
        pattern = f"{self.service_prefix}:cache:{namespace}:*"
        deleted_count = 0
        try:
            async for key in self.redis.scan_iter(match=pattern, count=1000):
                await self.redis.delete(key)
                deleted_count += 1
                
            self.logger.info(f"Cleared: {deleted_count} keys in namespace: '{namespace}'")
            return True
           
        except Exception as e:
            self.logger.error(f"Error clearing namespace '{namespace}': {str(e)}", exc_info=True)
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
    async def is_rate_limited(self, request: Request,times: int = 100, seconds: int = 60) -> bool | Exception:
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
                client_ip=request.client.host, 
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
        



    
    




