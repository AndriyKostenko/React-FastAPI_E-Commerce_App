from datetime import datetime
from contextlib import asynccontextmanager

from uvicorn import run
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError

from shared.shared_instances import (notification_service_redis_manager,
                                    notification_service_database_session_manager,
                                    logger,
                                    settings
)
from shared.exceptions.base_exceptions import (BaseAPIException, RateLimitExceededError)
from routes.notification_routes import notification_routes
from tasks.broker import taskiq_broker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.NOTIFICATION_SERVICE_APP_PORT}...")
    if not taskiq_broker.is_worker_process:
        await taskiq_broker.startup()
        logger.info("TaskIQ broker started successfully.")
    await notification_service_redis_manager.connect()
    logger.info("Redis health check passed.")
    await notification_service_database_session_manager.init_db()
    logger.info("Database initialized successfully.")
    logger.info('Server startup complete!')

    yield

    await notification_service_database_session_manager.close()
    logger.warning("Database connection closed on shutdown!")
    await notification_service_redis_manager.close()
    logger.warning("Cache connection closed on shutdown!")
    if not taskiq_broker.is_worker_process:
        await taskiq_broker.shutdown()
        logger.info("TaskIQ broker shut down successfully.")
    logger.warning("Server has shut down !")



app = FastAPI(
    title="notification-service",
    description="This is a notification service for managing user notifications.",
    version="0.0.1",
    lifespan=lifespan
)


_INTERNAL_PATHS = frozenset({"/metrics", "/health"})

# RFC-1918 private ranges used by Docker bridge/overlay networks.
# Any caller whose IP falls in these ranges is inside the Docker network
# and is a trusted internal service — skip Host-header validation for them.
_PRIVATE_PREFIXES = ("10.", "172.", "192.168.")


def _is_internal_client(request) -> bool:
    client_host = request.client.host if request.client else ""
    return (
        request.url.path in _INTERNAL_PATHS
        or any(client_host.startswith(p) for p in _PRIVATE_PREFIXES)
    )


@app.middleware("http")
async def host_validation_middleware(request: Request, call_next):
    """
    Validates the HTTP Host header against ALLOWED_HOSTS to prevent DNS-rebinding
    attacks.

    Bypassed for:
    - /metrics and /health  — scraped by Prometheus/cAdvisor via Docker DNS
    - Any RFC-1918 client IP — internal service-to-service calls (e.g. admin-js
      calling /api/v1/admin/schema/* on product-service) where the Host header
      is the Docker service name, not a public hostname
    """
    if settings.DEBUG_MODE or _is_internal_client(request):
        return await call_next(request)

    host = request.headers.get("host", "").split(":")[0]
    if host in settings.ALLOWED_HOSTS:
        return await call_next(request)

    logger.warning(f"Invalid Host header: {host} from {request.client.host}")
    raise HTTPException(
        status_code=400,
        detail="Invalid Host header",
        headers={"X-Error": "Invalid Host header"}
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
            "service": "notification-service"
        },
        status_code=200,
        headers={"Cache-Control": "no-cache"}
    )


def add_exception_handlers(app: FastAPI):
    """
    This function adds exception handlers to the FastAPI application.
    """

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Custom exception handler for Pydantic validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(ResponseValidationError)
    async def validation_response_exception_handler(request: Request, exc: ResponseValidationError):
        """Custom exception handler for response validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation response error",
                "errors": [{"field": err["loc"][-1] if err.get("loc") else "unknown", "message": err.get("msg", "Unknown validation error")} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(RequestValidationError)
    async def validation_request_exception_handler(request: Request, exc: RequestValidationError):
        """Custom exception handler for request validation errors"""
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
        """Base exception handler for all custom API exceptions"""
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
        """Custom exception handler for rate limit exceeded errors"""
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "detail": exc.detail,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )


# adding exception handlers to the app
add_exception_handlers(app)


# CORS or "Cross-Origin Resource Sharing" is a mechanism that
# allows restricted resources on a web page to be requested from another domain
# outside the domain from which the first resource was served.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)

# including all the routers to the app
app.include_router(notification_routes, prefix=settings.NOTIFICATION_SERVICE_URL_API_VERSION)


if __name__ == "__main__":
    run("main:app",
        host=settings.APP_HOST,
        port=settings.NOTIFICATION_SERVICE_APP_PORT,
        reload=True)
