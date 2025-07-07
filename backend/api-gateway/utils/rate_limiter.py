from webbrowser import get
from fastapi import Request
from redis import asyncio as aioredis

from utils.logger_config import setup_logger
from config import get_settings




class GlobalApiGatewayRateLimiter:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.logger = setup_logger(__name__)

    async def is_rate_limited(self, request: Request) -> bool:
        # Global reate limit (e.g. 1000 requests per minute per ip)
        client_ip = request.client.host
        global_key = f"global_rate_limit:{client_ip}"
        
        # service-specific rate limit (e.g. 100 requests per minute per ip for each service)
        service = request.path_params.get("service_name")
        
        self.logger.debug(f"Getting service_name: {service}")
        
        service_key = f"service_rate_limit:{service}:{client_ip}"
        
        # Check global rate limit
        global_pipe = self.redis.pipeline()
        global_pipe.incr(global_key)
        global_pipe.incr(service_key)
        global_pipe.expire(global_key, 60) # 1 minute window
        global_pipe.expire(service_key, 60)
        
        result = await global_pipe.execute()
        global_requests, service_requests = result[0], result[1]
        
        # Check if the global or service-specific rate limit is exceeded 1000 requests globally or 100 requests for a specific service
        return global_requests > 1000 or service_requests > 100