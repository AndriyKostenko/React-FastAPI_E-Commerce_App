import json
import logging
from typing import Any, Callable, TypeVar
from functools import wraps
from aiocache import RedisCache
from src.config import settings
from pydantic import EmailStr
from datetime import datetime
from uuid import UUID
from src.utils.logger_config import setup_logger

# Set up logging
logger = setup_logger(__name__)
T = TypeVar('T')  # For return type annotation

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for UUID, Email and datetime objects"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (UUID, EmailStr)):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
    
# Short TTL for user data = 60 , loger ttl for static data = 3600
def cache_response(namespace: str, key: str, ttl: int = 60) -> Callable:
    """
    Decorator to cache the response of an async function.
    
    Args:
        namespace: Namespace for the cache key
        key: Parameter name to use as cache key
        ttl: Time to live in seconds
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = RedisCache(
            endpoint=settings.REDIS_ENDPOINT,
            port=settings.REDIS_PORT,
            db=0
        )
                
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            cache_key = f"{namespace}:{kwargs.get(key)}"
            logger.debug(f"Cache key: {cache_key}")
            
            try:
                cached_data = await cache.get(cache_key)
                logger.debug(f"Cache hit: {bool(cached_data)}")
                
                if cached_data:
                    logger.debug(f"Returning cached data for key: {cache_key}")
                    return json.loads(cached_data)
                
                # Cache miss - execute function
                logger.debug(f"Cache miss for key: {cache_key}")
                response = await func(*args, **kwargs)
                
                # Prepare and cache data, if its a Pydantic model, use model_dump
                response_dict = (
                    response.model_dump() 
                    if hasattr(response, "model_dump") 
                    else response
                )
                cached_data = json.dumps(response_dict, cls=CustomJSONEncoder)
                
                await cache.set(
                    cache_key,
                    cached_data,
                    ttl=ttl
                )
                logger.debug(f"Cached data for key: {cache_key}")
                
                return response
                
            except Exception as e:
                logger.error(f"Cache error: {type(e).__name__} - {str(e)}")
                
                # anyway returning response if any exception reised
                return await func(*args, **kwargs)
            
                
        return wrapper
    return decorator


async def invalidate_cache(namespace: str, key: str) -> None:
    """
    Invalidate cache for a specific key.
    
    Args:
        namespace: Cache namespace
        key: Cache key to invalidate
    """
    cache = RedisCache(
        endpoint=settings.REDIS_ENDPOINT,
        port=settings.REDIS_PORT,
        db=0
    )
    cache_key = f"{namespace}:{key}"
    await cache.delete(cache_key)
    logger.info(f"Invalidated cache for key: {cache_key}")