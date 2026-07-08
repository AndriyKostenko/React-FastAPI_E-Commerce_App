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

from routes.supplier_routes import supplier_routes
from shared.exceptions.base_exceptions import BaseAPIException, RateLimitExceededError
from shared.middleware.logging_middleware import add_logging_middleware
from shared.telemetry import setup_tracing
from shared.shared_instances import (
    supplier_event_idempotency_service,
    supplier_service_redis_manager,
    supplier_service_database_session_manager,
    logger,
    settings,
    base_event_publisher,
)
from tasks.broker import taskiq_broker
from service_layer.outbox_poller_service import OutboxPollerService
from utils.seed_database import seed_default_supplier_config
from asyncio import create_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the supplier service."""
    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.SUPPLIER_SERVICE_APP_PORT}...")
    await supplier_service_redis_manager.connect()
    logger.info("Supplier service redis manager is connected.")
    await supplier_service_database_session_manager.init_db()
    logger.info("Supplier service DB session is started.")
    async with supplier_service_database_session_manager.transaction() as session:
        await seed_default_supplier_config(session=session, settings=settings)
        logger.info("Default supplier config seeded.")
    await base_event_publisher.start()
    logger.info("RabbitMQ Event publisher is started.")
    if not taskiq_broker.is_worker_process:
        await taskiq_broker.startup()
        logger.info("TaskIQ broker started successfully.")
    poller_task = create_task(OutboxPollerService().start_outbox_poller())
    logger.info("Supplier service outbox poller is started.")
    app.state.http_session = ClientSession()
    logger.info("Shared HTTP client session created.")
    logger.info("Supplier service startup complete!")

    yield

    await supplier_service_database_session_manager.close()
    logger.warning("Database connection closed on shutdown!")
    await base_event_publisher.stop()
    logger.warning("RabbitMQ connection is closed")
    if not taskiq_broker.is_worker_process:
        await taskiq_broker.shutdown()
        logger.info("TaskIQ broker shut down successfully.")
    poller_task.cancel()
    await app.state.http_session.close()
    logger.warning("Shared HTTP client session closed.")
    await supplier_service_redis_manager.close()
    logger.warning("Redis connection closed on shutdown!")
    logger.warning("Supplier service has shut down!")


app = FastAPI(
    title="supplier-service",
    description="Supplier integration service for fetching products and emitting import events.",
    version="0.1.0",
    lifespan=lifespan,
)

# opentelemetry tracing
# setup_tracing(app, service_name="supplier-service")

# init the prometheus metrics scraping
Instrumentator().instrument(app)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Records request latency into a multiprocess-safe histogram."""
    start = perf_counter()
    response = await call_next(request)
    duration = perf_counter() - start
    logger.debug(f"{request.method} {request.url.path} - {response.status_code} ({duration:.4f}s)")
    return response


@app.get("/health", tags=["Health Check"])
async def health_check():
    """A simple health check endpoint to verify that the service is running."""
    return JSONResponse(
        content={
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "supplier-service",
        },
        status_code=200,
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Multiprocess-aware Prometheus metrics endpoint."""
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
    """Add custom exception handlers to the FastAPI application."""

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(ResponseValidationError)
    async def validation_response_exception_handler(request: Request, exc: ResponseValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation response error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_request_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation request error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_exception_handler(request: Request, exc: RateLimitExceededError):
        return JSONResponse(
            status_code=429,
            content={
                "detail": exc.detail,
                "retry_after": exc.retry_after,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )


add_exception_handlers(app)
add_logging_middleware(app, service_name="supplier-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)

app.include_router(supplier_routes, prefix=settings.SUPPLIER_SERVICE_URL_API_VERSION)


if __name__ == "__main__":
    run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.SUPPLIER_SERVICE_APP_PORT,
        reload=settings.DEBUG_MODE,
    )
