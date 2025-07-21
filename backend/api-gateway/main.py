from contextlib import asynccontextmanager
from datetime import datetime

from fastapi.responses import JSONResponse
import uvicorn
from fastapi import FastAPI, Request, Response

from exceptions import BaseAPIException
from config import get_settings
from routes.user_routes import user_proxy
from shared.redis_manager import RedisManager


settings = get_settings()
redis_manager = RedisManager(service_prefix="api_gateway",
                             redis_url=settings.REDIS_URL,)




@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    app.state.rate_limiter = redis_manager
    app.state.cache_manager = redis_manager
    
    yield
    
    # Cleanup code can be added here if needed
    await redis_manager.close()


app = FastAPI(title="API Gateway", lifespan=lifespan)

@app.middleware("http")
async def gateway_middleware(request: Request, call_next) -> Response:
    """
    Middleware to handle rate limiting and caching for the API Gateway.
    """
    # 1. Global rate limit check
    # max 1000 requests per 1 minute
    await app.state.rate_limiter.is_rate_limited(request, times=1000, seconds=60)

        
    # 2. Check if the response is cached (for GET requests)
    if request.method == "GET" and "Authorization" not in request.headers:
        cached_response = await app.state.cache_manager.get_cached_response(request)
        if cached_response:
            return cached_response
    
    # 3. Forward request to microservice
    response = await call_next(request)
    
    
    # 4. Cache the response if applicable
    if (request.method == "GET" 
        and response.status_code in [200, 304] 
        and response.headers.get("Cache-Control") != "no-cache"
        and "Authorization" not in request.headers):
        
        await app.state.cache_manager.cache_response(request, response)
        
    return response



   
@app.get("/health", tags=["Health Check"])  
async def health_check():
    """
    A simple health check endpoint to verify that the service is running.
    """
    return JSONResponse(
        content={
            "status": "ok", 
            "timestamp": datetime.now().isoformat(),
            "service": "api-gateway"
        },
        status_code=200
    )


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

# Include the user service proxy routes
app.include_router(user_proxy, prefix="/api/v1", tags=["User Service Proxy"])


if __name__ == "__main__":
    uvicorn.run("main:app",
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                reload=True)