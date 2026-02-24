from contextlib import asynccontextmanager
from datetime import datetime

from fastapi.responses import JSONResponse
import uvicorn
from fastapi import FastAPI, Request, Response

from exceptions import BaseAPIException
from routes.user_routes import user_proxy
from routes.product_routes import product_proxy
from routes.order_routes import order_proxy
from shared.shared_instances import (api_gateway_redis_manager,
                                     logger,
                                     settings)
from middleware.auth_middleware import auth_middleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.API_GATEWAY_SERVICE_APP_PORT}...")
    await api_gateway_redis_manager.connect()
    logger.info('Server startup complete!')

    yield

    # Cleanup on shutdown
    await api_gateway_redis_manager.close()
    logger.warning("Cache connection closed on shutdown!")
    logger.warning(f"Server has shut down !")


app = FastAPI(title="API Gateway", lifespan=lifespan)

# Auth middleware runs before gateway middleware and checks JWT tokens
@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """
    Authentication middleware to handle JWT tokens
    """
    logger.debug("Running authentication middleware...")
    return await auth_middleware.middleware(request, call_next)



@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """
    Middleware to handle rate limiting and caching for the API Gateway.
    Before i got the caching but it was causing issues with auth so removed it for now.
    """
    # 1. Global rate limit check (max 1000 requests per 1 minute)
    await api_gateway_redis_manager.is_rate_limited(request, times=1000, seconds=60)
    # 2. Forward request to microservice
    return await call_next(request)



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
        status_code=200,
        headers={"Cache-Control": "no-cache"}
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
app.include_router(user_proxy, prefix=settings.API_GATEWAY_SERVICE_URL_API_VERSION, tags=["User Service Proxy"])
app.include_router(product_proxy, prefix=settings.API_GATEWAY_SERVICE_URL_API_VERSION, tags=["Product Service Proxy"])
app.include_router(order_proxy, prefix=settings.API_GATEWAY_SERVICE_URL_API_VERSION, tags=["Order Service Proxy"])

if __name__ == "__main__":
    uvicorn.run("main:app",
                host=settings.APP_HOST,
                port=settings.API_GATEWAY_SERVICE_APP_PORT,
                reload=True)
