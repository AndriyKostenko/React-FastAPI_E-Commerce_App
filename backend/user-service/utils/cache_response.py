import json
from typing import Any, Callable, Optional
from functools import wraps

from aiocache import RedisCache
from aiocache.serializers import JsonSerializer
from pydantic import BaseModel 

from config import get_settings
from utils.logger_config import setup_logger

# getting settings from config
settings = get_settings()

class CacheManager:
    """
    Cache manager for FastAPI endpoints with Redis backend.
    Handles caching, invalidation, and provides a decorator for easy use.
    """
    def __init__(self, redis_endpoint: str, redis_port: int, redis_db: int):
        """
        Initialize the cache manager with Redis connection details.
        
        Args:
            redis_endpoint: Redis server host/endpoint
            redis_port: Redis server port
            redis_db: Redis database number
            namespace: Namespace for cache keys
            ttl: Time-to-live for cached items in seconds
            serializer: Serializer to use for caching (default is JsonSerializer)
        """
        self.logger = setup_logger(__name__)
        self._redis: Optional[RedisCache] = None
        self.redis_endpoint = redis_endpoint
        self.redis_port = redis_port
        self.redis_db = redis_db
        self._serializer = JsonSerializer()
        
    # property to lazily initialize RedisCache
    @property
    def redis(self) -> RedisCache:
        """Lazy-loaded Redis connection"""
        if self._redis is None:
            try:
                self._redis = RedisCache(
                    endpoint=self.redis_endpoint,
                    port=self.redis_port,
                    db=self.redis_db,
                )
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis connection: {str(e)}")
                raise 
        self.logger.debug(f"Using Redis connection: {self._redis}")
        # Return the RedisCache instance
        # This allows us to use self.redis to access the RedisCache instance
        return self._redis
    
    
    async def is_connected(self) -> bool:
        """Check if Redis connection is alive"""
        try:
            await self.redis.raw("ping")
            return True
        except Exception as e:
            self.logger.error(f"Redis connection check failed: {str(e)}")
            return False
    
    @staticmethod
    def prepare_data_for_caching(data: Any) -> Any:
        """Prepare data for caching by converting to serializable format"""
        if isinstance(data, BaseModel):
            # If data is a Pydantic model, use model_dump_json() for serialization
            return data.model_dump_json()
        if hasattr(data, "dict"):
            # Convert to dict and then to JSON to ensure consistency for old pydantic versions
            return json.dumps(data.dict())
        # For other types, ensure JSON serialization
        return json.dumps(data)
        
    
    def cached(self, namespace: str, key: str, ttl: int) -> Callable:
        """
        Decorator for caching endpoint responses.
        
        Args:
            namespace: Cache namespace (e.g., 'users')
            key: Parameter name to use as cache key
            ttl: Time to live in seconds or callable that returns ttl
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                # getting the cache key from function params
                key_value = kwargs.get(key)
                
                if key_value is None:
                    self.logger.error(f"Key '{key}' not found in arguments. Cannot cache response.")
                    return await func(*args, **kwargs)
                if not namespace:
                    self.logger.error(f"Namespace '{namespace}' not found in arguments. Cannot cache response.")
                    return await func(*args, **kwargs)
                if not ttl:
                    self.logger.error(f"TTL '{ttl}' not found in arguments. Cannot cache response.")
                    return await func(*args, **kwargs)
                
                cache_key = f"{namespace}:{key_value}"
                
                try:
                    # getting chached data
                    cached_data = await self.redis.get(cache_key)
                    
                    if cached_data is not None:
                        self.logger.debug(f"Returning cached data : {cached_data}")
                        return cached_data
                
                    # Cache is missing -> execute the function
                    # Getting the response via Pydantic model
                    response = await func(*args, **kwargs)
                    
                    # preparing data for caching
                    to_cache = self.prepare_data_for_caching(response)
                    
                    self.logger.debug(f"Data for caching after serialization: {to_cache}")
                    
                    #caching the response
                    await self.redis.set(
                        cache_key,
                        to_cache, # Ensure JSON string storage
                        ttl=ttl
                    )
                    
                    return response
                
                except Exception as e:
                    self.logger.error(f"Cache error for {cache_key}: {str(e)}", exc_info=True)
                    # Return the original response if any exception occurs
                    return await func(*args, **kwargs)
                                      
            return wrapper
        return decorator
    
    
    async def invalidate_cache(self, namespace: str, key: str) -> bool:
        """
        Invalidate cache for a specific key in the given namespace.
        
        Args:
            namespace: Cache namespace (e.g., 'users')
            key: Cache key to invalidate
        """
        if not namespace or not key:
            self.logger.error(f"Namespace: {namespace} and key: {key} must be provided for cache invalidation.")
            return False
        
        # Construct the cache key
        cache_key = f"{namespace}:{key}"
    
        success = await self.redis.delete(cache_key)
        if success:
            self.logger.info(f"Invalidated cache for key: {cache_key}")
            return True
        else:
            self.logger.warning(f"Cache key not found for invalidation: {cache_key}")
            return False
        
        
    async def clear_namespace(self, namespace: str) -> bool:
        """
        Clear all keys in a namespace (using Redis SCAN for safety with large datasets)
        
        Args:
            namespace: The namespace to clear
            
        Returns:
            bool: True if operation was successful, False otherwise
        """
        if not namespace:
            self.logger.error("Namespace must be provided for clearing cache.")
            return False
        
        pattern = f"{namespace}:*"
        deleted_count = 0
        
        try:
            cursor = 0  # Start with cursor 0
            while True:
                cursor, keys = await self.redis.raw("scan", cursor, match=pattern, count=1000)
                
                if keys:
                    # Delete found keys in batches
                    await self.redis.delete(*keys)
                    deleted_count += len(keys)
                
                # Convert cursor from bytes to int
                cursor = int(cursor)
                if cursor == 0:  # Redis returns 0 when scan is complete
                    break
                    
            self.logger.info(f"Cleared {deleted_count} keys from namespace '{namespace}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing namespace '{namespace}': {str(e)}", exc_info=True)
            return False
    
    
    async def close(self) -> None:
        """Close the Redis connection"""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        


cache_manager = CacheManager(
    redis_endpoint=settings.REDIS_ENDPOINT,
    redis_port=settings.REDIS_PORT,
    redis_db=settings.REDIS_DB
)
    
    




