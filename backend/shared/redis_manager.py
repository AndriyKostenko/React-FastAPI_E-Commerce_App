import json
from typing import Any, Callable, Optional
from functools import wraps
from time import perf_counter
from math import ceil

from fastapi import Request
from fastapi.responses import JSONResponse
from redis import asyncio as aioredis
from shared.logger_config import setup_logger
from shared.base_exceptions import BaseAPIException, RateLimitExceededError





class RedisManager:
    """
    Unified Redis manager for caching and rate limiting across microservices.
    Provides decorators for both caching and rate limiting functionality.
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
    
    def _generate_cache_key(self, request: Request) -> str:
        client_ip = request.client.host
        endpoint = request.url.path
        return f"{self.service_prefix}:cache:{client_ip}:{endpoint}"
        
    # default caching for each api-gateway proxy is 5 mins
    async def cache_response(self, request: Request, response, ttl: int = 300):
        """
        Cache a response for a given request.
        For usage in API Gateway middleware
        """
        
        # Skip streaming responses
        if hasattr(response, 'body_iterator'):
            self.logger.debug("Skipping cache for streaming response")
            return
        
        try:
            if hasattr(response, "body"):
                response_body = response.body
            elif hasattr(response, "content"):
                response_body = response.content
            else:
                self.logger.warning(f"Unknown response type: {type(response)}")
                return
            
            # Convert bytes to string if needed  
            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8") 
                           
            cache_key = self._generate_cache_key(request)
            self.logger.debug(f"Caching response for key: {cache_key}")
            
            json_dict = json.loads(response.body)
            status_code = getattr(response, "status_code")
            
            await self.redis.setex(cache_key, ttl, json.dumps({"data": json_dict,
                                                               "status_code": status_code}))
            return 
        except json.JSONDecodeError:
            self.logger.warning(f"Cannot cache non-JSON response for: {cache_key}")
            return
        except Exception as e:
            self.logger.error(f"Error caching response: {str(e)}")
            return
        
          
    
    async def get_cached_response(self, request: Request) -> Optional[JSONResponse]:
        """
        Check if a response for this request is cached and return it.
        For use in API Gateway middleware.
        """
        
        try:
            cache_key = self._generate_cache_key(request=request)
            cached_data = await self.redis.get(cache_key)
            
            if cached_data:
                cached_dict = json.loads(cached_data)
                self.logger.debug(f"Gateway returnes cached data for: {cache_key}")
                return JSONResponse(content=cached_dict["data"],
                                    status_code=cached_dict["status_code"])
        
        except Exception as e:
            self.logger.error(f"Error retrieving from cache: {str(e)}")
        
        return None
            
    
    def cached(self, ttl: int) -> Callable:
        """
        Decorator for caching endpoint responses.
        
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
                    if cached_data is not None:
                        self.logger.debug(f"Returning cached data : {cached_data}")
                        return JSONResponse(
                            content=json.loads(cached_data["data"]),
                            status_code=cached_data["status_code"]
                        )
                    # Getting the fresh data
                    response = await func(*args, **kwargs)
                    self.logger.debug(f"Caching response for key: {cache_key}")
                    # serializing data to json (all data passed as a Pydantic)
                    to_cache = response.model_dump_json()
                    # getting status code
                    status_code = getattr(response, "status_code")
                    await self.redis.setex(cache_key, 
                                           ttl , 
                                           json.dumps({"data": to_cache, "status_code": status_code}))
                
                    return response
                
                # monitoring only base exception for all custom errors coz all of them inhereted from it 
                except BaseAPIException as e:
                    self.logger.debug(f"Not caching error reponse: {str(e)}")
                    # not chaching and re-rasing an error
                    raise

            return wrapper
        return decorator
    
    
    async def invalidate_cache(self, namespace: str, key: str) -> bool:
        """
        Invalidate cache for a specific key in the given namespace.
        """
        if not namespace or not key:
            self.logger.error(f"Namespace: {namespace} and key: {key} must be provided for cache invalidation.")
            return False
        # Construct the cache key
        cache_key = f"{self.service_prefix}:cache:{namespace}:{key}"
    
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
    
    def ratelimiter(self, times: int = 10, seconds: int = 60) -> Callable:
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
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
        except Exception as e:
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
        



    
    




