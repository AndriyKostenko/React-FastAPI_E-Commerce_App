from contextlib import asynccontextmanager
from datetime import datetime

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn import run
from fastapi import FastAPI, Request, Response

from shared.exceptions.base_exceptions import BaseAPIException
from routes.user_routes import user_proxy
from routes.product_routes import product_proxy
from routes.order_routes import order_proxy
from routes.notification_routes import notification_proxy
from routes.payment_routes import payment_proxy
from shared.shared_instances import (api_gateway_redis_manager,
                                     logger,
                                     settings)
from middleware.auth_middleware import auth_middleware
from gateway.apigateway import api_gateway_manager


# ---------------------------------------------------------------------------
# Cache-invalidation helper
# ---------------------------------------------------------------------------

# Ordered from most-specific to least-specific so the first match wins.
_INVALIDATION_NAMESPACE_MAP: list[tuple[str, str]] = [
    ("products/detailed", "products"),
    ("/products", "products"),
    ("/categories", "categories"),
    ("/images", "images"),
    ("/reviews", "reviews"),
    ("/orders", "orders"),
    ("/users", "users"),
    ("/notifications", "notifications"),
]


def _get_invalidation_namespace(path: str) -> str | None:
    """Return the cache namespace that should be invalidated after a successful mutation on *path*."""
    path_lower = path.lower()
    for segment, namespace in _INVALIDATION_NAMESPACE_MAP:
        if segment in path_lower:
            return namespace
    return None


# Default cache TTL for gateway-level GET response caching (seconds).
_CACHE_TTL_MAP: list[tuple[str, int]] = [
    ("/products/detailed", 600),
    ("/products", 300),
    ("/categories", 300),
    ("/images", 300),
    ("/reviews", 300),
]
_DEFAULT_CACHE_TTL = 300


def _get_cache_ttl(path: str) -> int:
    path_lower = path.lower()
    for segment, ttl in _CACHE_TTL_MAP:
        if segment in path_lower:
            return ttl
    return _DEFAULT_CACHE_TTL


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.API_GATEWAY_SERVICE_APP_PORT}...")
    await api_gateway_redis_manager.connect()
    await api_gateway_manager.startup()
    logger.info('Server startup complete!')

    yield

    # Cleanup on shutdown
    await api_gateway_manager.shutdown()
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
    Gateway middleware: global rate limiting, response caching, and cache invalidation.
    """
    # 1. Global rate limit (1 000 requests per minute per IP)
    await api_gateway_redis_manager.is_rate_limited(request, times=1000, seconds=60)

    # 2. Serve from cache for public GET requests (no auth credentials present)
    cached_response = await api_gateway_redis_manager.get_cached_response(request)
    if cached_response:
        return cached_response

    # Determine auth state once — used to decide whether to cache the response
    is_authenticated = (
        "Authorization" in request.headers
        or request.cookies.get("access_token") is not None
    )

    # 3. Forward request to the downstream microservice
    response: Response = await call_next(request)

    # 4. Cache successful GET responses; invalidate stale namespaces on mutations
    if 200 <= response.status_code < 300:
        if request.method == "GET" and not is_authenticated:
            # Consume the streaming body — mandatory before the iterator is exhausted
            body = b"".join([chunk async for chunk in response.body_iterator])
            ttl = _get_cache_ttl(request.url.path)
            await api_gateway_redis_manager.cache_response(request, body, response.status_code, ttl=ttl)
            # Reconstruct response since body_iterator is now consumed
            response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
            namespace = _get_invalidation_namespace(request.url.path)
            if namespace:
                await api_gateway_redis_manager.invalidate_namespace(namespace)

    return response


# CORS must be added AFTER @app.middleware decorators — Starlette builds the stack
# in LIFO order, so the last add_middleware call becomes the outermost layer.
# This ensures CORS headers are present on ALL responses, including auth 401s.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)



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
app.include_router(notification_proxy, prefix=settings.API_GATEWAY_SERVICE_URL_API_VERSION, tags=["Notification Service Proxy"])
app.include_router(payment_proxy, prefix=settings.API_GATEWAY_SERVICE_URL_API_VERSION, tags=["Payment Service Proxy"])

if __name__ == "__main__":
    run("main:app",
        host=settings.APP_HOST,
        port=settings.API_GATEWAY_SERVICE_APP_PORT,
        reload=True)
