import os
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response as PlainResponse
from uvicorn import run
from fastapi import FastAPI, Request, HTTPException
from httpx import RequestError
from prometheus_client import CollectorRegistry, generate_latest, multiprocess, REGISTRY, Histogram, Counter

from shared.exceptions.base_exceptions import BaseAPIException
from shared.middleware.logging_middleware import add_logging_middleware
from shared.telemetry import setup_tracing
from routes.user_routes import user_proxy
from routes.product_routes import product_proxy
from routes.order_routes import order_proxy
from routes.notification_routes import notification_proxy
from routes.payment_routes import payment_proxy
from shared.shared_instances import (api_gateway_cache_manager,
                                     api_gateway_rate_limit_manager,
                                     logger,
                                     settings)
from middleware.auth_middleware import auth_middleware
from gateway.apigateway import api_gateway_manager
from middleware.cache_middleware import GatewayRequestMiddleware



"""
Request  →  logging → CORS → authentication_middleware → gateway_middleware → route

Response ←  logging ← CORS ← authentication_middleware ← gateway_middleware ← route
"""

REQUEST_COUNTER: Counter | None = None
LATENCY_COUNTER: Histogram | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    global REQUEST_COUNTER
    global LATENCY_COUNTER

    REQUEST_COUNTER = Counter(
        "gateway_requests_total",
        "Total HTTP requests at API Gateway",
        ["method", "path", "status"],
    )

    LATENCY_COUNTER = Histogram(
        "gateway_request_duration_seconds",
        "Gateway request latency",
        ["method", "path"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    )



    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.API_GATEWAY_SERVICE_APP_PORT}...")
    await api_gateway_cache_manager.connect()
    await api_gateway_rate_limit_manager.connect()
    await api_gateway_manager.startup()
    logger.info('Server startup complete!')

    yield

    # Cleanup on shutdown
    await api_gateway_manager.shutdown()
    await api_gateway_cache_manager.close()
    await api_gateway_rate_limit_manager.close()
    logger.warning("Cache connection closed on shutdown!")
    logger.warning(f"Server has shut down !")


# initializing the main app instance
app = FastAPI(title="API Gateway", lifespan=lifespan)

# Instantiate the class-based gateway middleware (holds CacheManager + RateLimitManager).
gateway_request_middleware = GatewayRequestMiddleware(
    cache_manager=api_gateway_cache_manager,
    rate_limit_manager=api_gateway_rate_limit_manager,
)


# initializing the OpenTelemetry tracing
setup_tracing(app, service_name="api-gateway", instrument_sqlalchemy=False)



# Ratelimiting and caching middleware on each request
# Registered first → becomes the inner layer, runs AFTER authentication_middleware.
# This ensures auth is always validated before cache is consulted or rate limits are tracked.
@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """
    Gateway middleware: global rate limiting, response caching, and cache invalidation.
    Monitoring paths bypass all gateway logic — they must never be rate-limited or cached.
    """

    if request.url.path in ("/metrics", "/health"):
        return await call_next(request)

    is_public = auth_middleware.is_public_endpoint(request.url.path, request.method)
    start = perf_counter()
    response = await gateway_request_middleware(request, call_next, is_public=is_public)
    duration = perf_counter() - start

    if REQUEST_COUNTER and LATENCY_COUNTER:
        REQUEST_COUNTER.labels(
            method=request.method,
            path=request.url.path,
            status=f"{response.status_code // 100}xx",
        ).inc()
        LATENCY_COUNTER.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration)

    return response


# Auth middleware registered second → becomes the outer layer, runs FIRST on every request.
# This guarantees tokens are validated before cache lookups or rate limiting.
@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """
    Authentication middleware to handle JWT tokens
    """
    logger.debug("Running authentication middleware...")
    return await auth_middleware.middleware(request, call_next)


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

# adding the logging
add_logging_middleware(app, service_name="api-gateway")



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

@app.get("/metrics", include_in_schema=False)
def metrics():
    """Multiprocess-aware Prometheus metrics endpoint."""
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

    if multiproc_dir:
        # Multi-worker: merge all worker .db files from the shared dir
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        # Single process (local dev): use the default registry directly
        registry = REGISTRY

    return PlainResponse(
        content=generate_latest(registry),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/media/{file_path:path}", include_in_schema=False)
async def proxy_product_media(file_path: str):
    """
    Proxy product-service static media through API Gateway so frontend can use a
    single API origin (:8000) for both JSON APIs and generated image files.
    """
    normalized_path = file_path.lstrip("/")
    if not normalized_path:
        raise HTTPException(status_code=404, detail="Media file not found")

    upstream_url = f"{settings.PRODUCT_SERVICE_URL.rstrip('/')}/media/{normalized_path}"
    try:
        upstream_response = await api_gateway_manager.client.get(
            upstream_url,
            timeout=api_gateway_manager._TIMEOUT,
        )
    except RequestError as exc:
        logger.error(f"Failed to fetch media from product-service ({upstream_url}): {exc!r}")
        raise HTTPException(status_code=502, detail="Failed to fetch media file")

    passthrough_headers: dict[str, str] = {}
    for header in ("cache-control", "etag", "last-modified", "accept-ranges", "content-range"):
        value = upstream_response.headers.get(header)
        if value:
            passthrough_headers[header] = value

    return PlainResponse(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
        headers=passthrough_headers,
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
