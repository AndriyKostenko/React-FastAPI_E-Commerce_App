from functools import wraps
from time import time

from fastapi import Request
from redis import asyncio as aioredis

from errors import RateLimitExceededError
from config import get_settings
from utils.logger_config import setup_logger


class RateLimiter:
    def __init__(self, times: int, seconds: int):
        """
        Initialize the rate limiter with a maximum number of requests and a time window.
        :param times: Maximum number of requests allowed in the time window.
        :param secomns: Time window in seconds.
        """
        self.logger = setup_logger(__name__)
        self.settings = get_settings()
        self.times = times
        self.seconds = seconds
        self.redis = aioredis.from_url(
            f"redis://{self.settings.REDIS_ENDPOINT}:{self.settings.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True
        )
        
    def _generate_key(self, request: Request) -> str:
        """
        Generate a unique key for the request based on the client's IP address.
        :param request: FastAPI Request object.
        :return: Unique key for the request.
        """
        self.logger.debug(f"Generating rate limit key for request: {request.client.host} : {request.url.path}")
        return f"rate_limit:{request.client.host}:{request.url.path}"
    
    async def _check_rate_limit(self, key: str):
        """
        Check if the rate limit is excedeed
        """
        pipe = self.redis.pipeline()
        now = time()
        
        # add current request timestamp
        pipe.zadd(key, {str(now): now})
        # remove old request outside the window
        pipe.zremrangebyscore(key, 0, now - self.seconds)
        # count requests in current window
        pipe.zcard(key)
        # set key expiration
        pipe.expire(key, self.seconds)
        
        # execute the pipeline
        results = await pipe.execute()
        
        # results[0] is the result of zadd, we don't need it
        # results[1] is the result of zremrangebyscore, we don't need it
        # results[2] is the count of requests in the current window
        request_count = results[2]
        
        # check if the request count is within the limit
        return request_count <= self.times
    
    
    # getting reauest from the FastAPI endpoint parameters
    async def __call__(self, request: Request):
        """
        Middleware-style callable for rate limiting
        """
        #generating the key
        key = self._generate_key(request)
        
        # check if the rate limit is exceeded
        if not await self._check_rate_limit(key):
            self.logger.warning(f"Rate limit exceeded for: {key}")
            raise RateLimitExceededError(client_ip=request.client.host, retry_after=self.seconds)
 
            
  
        
        
def ratelimiter(times: int = 10, seconds: int = 60):
    """
    Decorator to apply rate limiting to a FastAPI route.
    :param times: Maximum number of requests allowed in the time window.
    :param seconds: Time window in seconds.
    :return: Decorated function with rate limiting applied.
    """
    limiter = RateLimiter(times=times, seconds=seconds)
    
    def decorator(func):
        @wraps(func)
        # getting "request" from the FastAPI endpoint parameters
        async def wrapper(*args, request: Request, **kwargs):
            await limiter(request)
            # call the original function if rate limit is not exceeded
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator
        