from datetime import datetime
from contextlib import asynccontextmanager
from asyncio import create_task

from uvicorn import run
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError

from service_layer.outbox_poller_service import OutboxPollerService
from routes.payment_routes import payment_routes
from shared.exceptions.base_exceptions import BaseAPIException, RateLimitExceededError
from shared.shared_instances import (
    payment_event_idempotency_service,
    payment_service_redis_manager,
    payment_service_database_session_manager,
    logger,
    settings,
    base_event_publisher,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Payment service starting on {settings.APP_HOST}:{settings.PAYMENT_SERVICE_APP_PORT}...")
    await payment_service_redis_manager.connect()
    await payment_event_idempotency_service.connect()
    await payment_service_database_session_manager.init_db()
    await base_event_publisher.start()
    logger.info("RabbitMQ Event publisher started.")
    poller_task = create_task(OutboxPollerService().start_outbox_poller())
    logger.info("Outbox poller task created.")
    logger.info("Payment service startup complete!")

    yield

    await payment_service_database_session_manager.close()
    logger.warning("Database connection closed on shutdown!")
    await payment_service_redis_manager.close()
    logger.warning("Redis cache connection closed on shutdown!")
    await base_event_publisher.stop()
    logger.warning("RabbitMQ Event publisher stopped.")
    poller_task.cancel()
    logger.warning("Outbox poller cancelled.")
    logger.warning("Payment service shut down!")


app = FastAPI(
    title="payment-service",
    description="Stripe payment processing service: creates PaymentIntents and handles webhooks.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def host_validation_middleware(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    if settings.DEBUG_MODE or host in settings.ALLOWED_HOSTS:
        return await call_next(request)
    logger.warning(f"Invalid Host header: {host} from {request.client}")
    raise HTTPException(status_code=400, detail="Invalid Host header")


@app.get("/health", tags=["Health Check"])
async def health_check():
    return JSONResponse(
        content={
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "payment-service",
        },
        status_code=200,
        headers={"Cache-Control": "no-cache"},
    )


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": [
                    {"field": err["loc"][-1] if err.get("loc") else "unknown",
                     "message": err.get("msg", "Unknown validation error")}
                    for err in exc.errors()
                ],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(ResponseValidationError)
    async def response_validation_handler(request: Request, exc: ResponseValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation response error",
                "errors": [
                    {"field": err["loc"][-1] if err.get("loc") else "unknown",
                     "message": err.get("msg", "Unknown validation error")}
                    for err in exc.errors()
                ],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation request error",
                "errors": [
                    {"field": err["loc"][-1] if err.get("loc") else "unknown",
                     "message": err.get("msg", "Unknown validation error")}
                    for err in exc.errors()
                ],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
            },
        )

    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "detail": exc.detail,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
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
                "path": request.url.path,
            },
        )


add_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)

app.include_router(payment_routes, prefix=settings.PAYMENT_SERVICE_URL_API_VERSION)


if __name__ == "__main__":
    run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.PAYMENT_SERVICE_APP_PORT,
        reload=True,
    )
