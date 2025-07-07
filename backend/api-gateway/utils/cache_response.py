from aiocache import cached
from fastapi import Request
from redis import asyncio as aioredis
from utils.logger_config import setup_logger


class GlobalCacheManager:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.logger = setup_logger(__name__)
        
    async def get_cached_response(self, request: Request) -> dict | None:
        # for now assuming we only cache GET requests
        # and that the cache key is based on the request URL
        if request.method != "GET":
            return None
        
        # Only cache public endpoints
        if "Authorization" in request.headers:
            return None
        
        cache_key = f"global_cache:{request.url.path}"
        self.logger.debug(f"Checking cache for key: {cache_key}")
        
        cached_response = await self.redis.get(cache_key)
        
        if cached_response:
            self.logger.debug(f"Cache hit for key: {cache_key}")
            return cached_response
        
        return 
        
        
    async def cache_response(self, request: Request, response_data: dict, ttl: int = 300) -> None:
        # for now assuming we only cache GET requests
        if request.method != "GET":
            return
        
        # Only cache public endpoints
        if "Authorization" in request.headers:
            return
        
        cache_key = f"global_cache:{request.url.path}"
        self.logger.debug(f"Caching response for key: {cache_key} with TTL: {ttl} seconds")
        await self.redis.setex(cache_key, ttl, response_data)