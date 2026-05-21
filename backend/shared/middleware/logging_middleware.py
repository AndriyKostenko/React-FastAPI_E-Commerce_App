"""
Structured HTTP logging middleware with distributed correlation IDs.

Usage in each service main.py (after all other middleware):

    from shared.middleware.logging_middleware import add_logging_middleware
    add_logging_middleware(app, service_name="user-service")

Every log record emitted anywhere in the request lifecycle will automatically
carry request_id and service fields via the _ContextFilter in logger_manager.
"""
import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# These are read by _ContextFilter in logger_manager so that every log line
# produced during a request automatically includes request_id + service.
REQUEST_ID_CTX_VAR: ContextVar[str] = ContextVar("request_id", default="-")
SERVICE_NAME_CTX_VAR: ContextVar[str] = ContextVar("service_name", default="unknown")

_logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({"/health", "/metrics", "/docs", "/openapi.json", "/redoc"})


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str) -> None:
        super().__init__(app)
        self.service_name: str = service_name

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        # Propagate an incoming correlation ID or generate a new one.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind to context so all loggers pick it up automatically.
        req_token = REQUEST_ID_CTX_VAR.set(request_id)
        svc_token = SERVICE_NAME_CTX_VAR.set(self.service_name)

        start = time.perf_counter()
        _logger.info(
            "request started",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "client_ip": request.client.host if request.client else "-",
            },
        )

        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _logger.exception(
                "request failed with unhandled exception",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            REQUEST_ID_CTX_VAR.reset(req_token)
            SERVICE_NAME_CTX_VAR.reset(svc_token)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        _logger.log(
            level,
            "request completed",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response


def add_logging_middleware(app: FastAPI, service_name: str) -> None:
    """Register the logging middleware as the outermost layer on *app*."""
    app.add_middleware(LoggingMiddleware, service_name=service_name)
