from contextlib import asynccontextmanager
from datetime import datetime

from fastapi.responses import JSONResponse
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from redis import asyncio as aioredis

from exceptions import BaseAPIException
from config import get_settings
from utils.rate_limiter import GlobalApiGatewayRateLimiter
from utils.cache_response import GlobalCacheManager



"""
This is the main entry point for the API Gateway service.

"""

settings = get_settings()


app = FastAPI(title="API Gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    redis_client = aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
        decode_responses=True,
        encoding="utf-8"
    )
    
    app.state.rate_limiter = GlobalApiGatewayRateLimiter(redis_client)
    app.state.cache_manager = GlobalCacheManager(redis_client)
    
    yield
    
    # Cleanup code can be added here if needed
    await redis_client.close()



@app.middleware("http")
async def gateway_middleware(request: Request, call_next) -> JSONResponse:
    """
    Middleware to handle rate limiting and caching for the API Gateway.
    """
    # 1. Global rate kimit check
    if await app.state.rate_limiter.is_rate_limited(request):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
        
    # 2. Check if the response is cached
    cached = await app.state.cache_manager.get_cached_response(request)
    if cached:
        return JSONResponse(content=cached)
    
    # 3. Forward request to microservice
    response = await call_next(request)
    
    # 4. Cache the response if applicable
    if response.status_code == 200 and response.headers.get("Cache-Control") != "no-cache":
        await app.state.cache_manager.cache_response(request, response.body)
        
    return response



   
@app.get("/health", tags=["Health Check"])  
async def health_check():
    """
    A simple health check endpoint to verify that the service is running.
    """
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


def add_exception_handlers(app: FastAPI):
    """
    This function adds exception handlers to the FastAPI application.
    """  
   
    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        """Base exception handler for all custom API exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={"detail": exc.detail,
                     "timestamp": datetime.now().isoformat(),
                     "path": request.url.path
            },
        )

        



# adding exception handlers to the app      
add_exception_handlers(app)


if __name__ == "__main__":
    uvicorn.run("main:app",
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                reload=True)