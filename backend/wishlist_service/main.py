import os
from datetime import datetime
from contextlib import asynccontextmanager
from time import perf_counter

from aiohttp import ClientSession
from uvicorn import run
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response as PlainResponse
from fastapi import FastAPI, Request, HTTPException
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError
from prometheus_client import CollectorRegistry, generate_latest, multiprocess, REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator

from routes.wishlist_routes import wishlist_routes
from shared.exceptions.base_exceptions import (BaseAPIException, RateLimitExceededError)
from shared.middleware.logging_middleware import add_logging_middleware
from shared.telemetry import setup_tracing
from shared.shared_instances import (wishlist_event_idempotency_service,
                                     wishlist_service_redis_manager,
                                     wishlist_service_database_session_manager,
                                     logger,
                                     settings,
                                     base_event_publisher)
from helpers.internal_access_helper import internal_access_helper
from helpers.request_helper import request_metrics_helper


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.WISHLIST_SERVICE_APP_PORT}...")
    request_metrics_helper.initialize()
    await wishlist_service_redis_manager.connect()
    await wishlist_event_idempotency_service.connect()
    await wishlist_service_database_session_manager.init_db()
    logger.info("Wishlist service DB session is started.")
    await base_event_publisher.start()
    logger.info("RabbitMQ Event publisher is started.")
    app.state.http_session = ClientSession()
    logger.info("Shared HTTP client session created.")
    logger.info('Server startup complete!')

    yield

    await wishlist_service_database_session_manager.close()
    logger.warning("Database connection closed on shutdown!")
    await wishlist_service_redis_manager.close()
    logger.warning("Redis Cache connection closed on shutdown!")
    await base_event_publisher.stop()
    logger.warning("RabbitMQ connection is closed")
    await app.state.http_session.close()
    logger.warning("Shared HTTP client session closed.")
    logger.warning(f"Server has shut down !")


app = FastAPI(
    title="wishlist-service",
    description="This is a wishlist service for managing user wishlists.",
    version="0.0.1",
    lifespan=lifespan,
)

setup_tracing(app, service_name="wishlist-service")

Instrumentator().instrument(app)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if internal_access_helper.is_internal_path(request.url.path):
        return await call_next(request)

    start = perf_counter()
    response = await call_next(request)
    duration = perf_counter() - start

    request_metrics_helper.observe(request=request, response=response, duration=duration)
    return response


@app.middleware("http")
async def host_validation_middleware(request: Request, call_next):
    if settings.DEBUG_MODE or internal_access_helper.is_internal_client(request):
        return await call_next(request)

    host = request.headers.get("host", "").split(":")[0]
    if host in settings.ALLOWED_HOSTS:
        return await call_next(request)

    logger.warning(f"Invalid Host header: {host} from {request.client}")
    raise HTTPException(
        status_code=400,
        detail="Invalid Host header",
        headers={"X-Error": "Invalid Host header"}
    )


@app.get("/health", tags=["Health Check"])
async def health_check():
    return JSONResponse(
        content={
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "wishlist-service"
        },
        status_code=200,
        headers={"Cache-Control": "no-cache"}
    )


@app.get("/metrics", include_in_schema=False)
def metrics():
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

    if multiproc_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY

    return PlainResponse(
        content=generate_latest(registry),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def add_exception_handlers(app: FastAPI):
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

    @app.exception_handler(ResponseValidationError)
    async def validation_response_exception_handler(request: Request, exc: ResponseValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation response error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_request_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation request error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={"detail": exc.detail,
                     "timestamp": datetime.now().isoformat(),
                     "path": request.url.path
            },
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(request: Request, exc: RateLimitExceededError):
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "detail": exc.detail,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )


add_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)
add_logging_middleware(app, service_name="wishlist-service")

app.include_router(wishlist_routes, prefix=settings.WISHLIST_SERVICE_URL_API_VERSION)


if __name__ == "__main__":
    run("main:app",
        host=settings.APP_HOST,
        port=settings.WISHLIST_SERVICE_APP_PORT,
        reload=True)
