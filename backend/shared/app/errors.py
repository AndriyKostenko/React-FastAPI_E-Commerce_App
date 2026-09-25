"""The error contract every service answers with.

Each ``main.py`` used to carry its own 70-line ``add_exception_handlers``: five
near-identical closures differing only in a ``detail`` string.  Collapsing them
into a registry of renderers also collapses the timestamp format, which had
drifted — the handlers emitted naive ``datetime.now()`` while ``/health`` emitted
proper UTC, so one service answered in two formats.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol, Self

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from shared.exceptions.base_exceptions import BaseAPIException, RateLimitExceededError


type PydanticError = ValidationError | RequestValidationError | ResponseValidationError


def utc_timestamp() -> str:
    """The one definition of the error timestamp format: always timezone-aware UTC."""
    return datetime.now(timezone.utc).isoformat()


def _field_errors(exc: PydanticError) -> list[dict[str, str]]:
    # Pydantic's ``loc`` is a tuple whose last element names the offending field.
    # It is empty for model-level errors, hence the "unknown" fallback.
    return [
        {
            "field": str(err["loc"][-1]) if err.get("loc") else "unknown",
            "message": err.get("msg", "Unknown validation error"),
        }
        for err in exc.errors()
    ]


class ExceptionRenderer[ExcT: Exception](Protocol):
    """Turns one exception into the response body the client sees."""

    def __call__(self, request: Request, exc: ExcT) -> JSONResponse: ...


def validation_renderer(detail: str) -> ExceptionRenderer[PydanticError]:
    """Build the renderer shared by the three Pydantic error types."""

    def render(request: Request, exc: PydanticError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": detail,
                "errors": _field_errors(exc),
                "timestamp": utc_timestamp(),
                "path": request.url.path,
            },
        )

    return render


def api_exception_renderer(request: Request, exc: BaseAPIException) -> JSONResponse:
    """Render any of our own API exceptions.

    ``RateLimitExceededError`` subclasses ``BaseAPIException`` and carries its own
    ``Retry-After`` header, so passing ``exc.headers`` through covers both.
    """
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "detail": exc.detail,
            "timestamp": utc_timestamp(),
            "path": request.url.path,
        },
    )


def integrity_error_renderer(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    A write that breaks a database constraint (a duplicate, a row still
    referenced elsewhere) is a conflict with existing data: 409, not 500.

    The database's message names tables and constraints, so it is never sent
    to the client. Deletes now flush at the call site, which is what lets this
    reach a handler instead of failing at commit after the response was chosen.
    """
    return JSONResponse(
        status_code=409,
        content={
            "detail": "The request conflicts with existing data",
            "timestamp": utc_timestamp(),
            "path": request.url.path,
        },
    )


class ExceptionHandlerRegistry:
    """Maps exception type to renderer, then installs the lot onto an app.

    A service needing one extra mapping calls ``register`` before ``install``
    rather than restating the whole default set.
    """

    def __init__(self, *, defaults: bool = True) -> None:
        """``defaults=False`` starts empty, for a service that answers a
        narrower contract — the gateway proxies upstream validation errors
        rather than rendering its own."""
        self._renderers: dict[type[Exception], ExceptionRenderer[Exception]] = {}
        if not defaults:
            return
        self._renderers = {
            ValidationError: validation_renderer("Validation error"),
            ResponseValidationError: validation_renderer("Validation response error"),
            RequestValidationError: validation_renderer("Validation request error"),
            BaseAPIException: api_exception_renderer,
            # Registered explicitly even though Starlette would find it via the
            # MRO, so the mapping stays readable and a future divergence is a
            # one-line change here.
            RateLimitExceededError: api_exception_renderer,
            IntegrityError: integrity_error_renderer,
        }

    def register[ExcT: Exception](
        self, exc_type: type[ExcT], renderer: ExceptionRenderer[ExcT]
    ) -> Self:
        self._renderers[exc_type] = renderer
        return self

    def install(self, app: FastAPI) -> None:
        for exc_type, renderer in self._renderers.items():
            app.add_exception_handler(exc_type, self._as_handler(renderer))

    @staticmethod
    def _as_handler(
        renderer: ExceptionRenderer[Exception],
    ) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
        """Adapt a sync renderer to the coroutine Starlette expects.

        The renderer is bound as a default argument rather than closed over, so
        each handler keeps its own renderer instead of every one of them seeing
        the last value of the loop variable.
        """

        async def handler(
            request: Request,
            exc: Exception,
            _render: ExceptionRenderer[Exception] = renderer,
        ) -> JSONResponse:
            return _render(request, exc)

        return handler
