"""Assembles one service's FastAPI application.

Every ``main.py`` performed the same assembly in the same order — tracing,
instrumentation, five middleware layers, metrics, health, exception handlers,
routers — and each copy was free to get the order subtly wrong, or to leave a
piece commented out. The Builder states that order once.

Where a service genuinely differs it says so out loud (``without_host_validation``
on the gateway) instead of differing by omission.
"""

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from logging import Logger
from typing import Self

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from shared.app.descriptor import ServiceDescriptor
from shared.app.errors import ExceptionHandlerRegistry
from shared.app.health import ReadinessProbe, build_health_router
from shared.app.instrumentation import (
    MONITORING_PATHS,
    InternalAccessHelper,
    RequestMetricsHelper,
    add_metrics_middleware,
    internal_access_helper,
)
from shared.app.metrics import build_metrics_router
from shared.middleware.host_validation_middleware import add_host_validation_middleware
from shared.middleware.logging_middleware import add_logging_middleware
from shared.settings import Settings
from shared.telemetry import setup_tracing


type LifespanFactory = Callable[[FastAPI], AbstractAsyncContextManager[None]]
"""What ``@asynccontextmanager`` produces: call with the app, use as a context."""

type HTTPMiddleware = Callable[[Request, Callable[..., object]], object]
"""A ``BaseHTTPMiddleware`` dispatch coroutine — ``(request, call_next)``."""


class ServiceAppBuilder[ResourcesT]:
    """Builds the ASGI app for one service.

    Generic over that service's resource container (``UserApiResources``,
    ``CartApiResources``, …) so the readiness probes and the request-scoped
    resolver stay type-checked against the real container rather than ``Any``.

    Usage::

        app = (
            ServiceAppBuilder[CartApiResources](DESCRIPTOR, settings=settings, logger=logger)
            .with_lifespan(cart_lifespan, resolve_resources)
            .with_readiness(DatabaseEngineProbe())
            .with_router(cart_routes, prefix=DESCRIPTOR.api_prefix)
            .build()
        )
    """

    def __init__(
        self,
        descriptor: ServiceDescriptor,
        *,
        settings: Settings,
        logger: Logger,
        internal_access: InternalAccessHelper = internal_access_helper,
    ) -> None:
        self._descriptor = descriptor
        self._settings = settings
        self._logger = logger
        self._internal_access = internal_access
        # One histogram per process, named after this service. Created here but
        # only *registered* during the lifespan, after any gunicorn fork.
        self._metrics = RequestMetricsHelper(descriptor.name)
        self._lifespan: LifespanFactory | None = None
        self._resolve: Callable[[Request], ResourcesT] | None = None
        self._probes: list[ReadinessProbe[ResourcesT]] = []
        self._routers: list[tuple[APIRouter, str, list[str] | None]] = []
        self._extra_middleware: list[tuple[type, dict[str, object]]] = []
        self._http_middleware: list[HTTPMiddleware] = []
        self._errors = ExceptionHandlerRegistry()
        self._instrument_sqlalchemy = True
        self._instrument_redis = True
        self._host_validation = True
        self._request_metrics = True
        self._instrumentator = True

    # ------------------------------ configuration ------------------------------

    def with_lifespan(
        self,
        factory: LifespanFactory,
        resolve: Callable[[Request], ResourcesT],
    ) -> Self:
        """Set the resource lifespan and the request-scoped resolver for it.

        ``resolve`` is what the readiness probes use to reach the container that
        ``factory`` attached to ``app.state``.
        """
        self._lifespan = factory
        self._resolve = resolve
        return self

    def with_readiness(self, *probes: ReadinessProbe[ResourcesT]) -> Self:
        self._probes.extend(probes)
        return self

    def with_router(
        self, router: APIRouter, prefix: str = "", tags: list[str] | None = None
    ) -> Self:
        self._routers.append((router, prefix, tags))
        return self

    def with_routers(self, routers: Sequence[APIRouter], prefix: str = "") -> Self:
        """Mount several routers under one prefix — the multi-router services."""
        for router in routers:
            self.with_router(router, prefix)
        return self

    def with_middleware(self, middleware_class: type, **options: object) -> Self:
        """Service-specific ASGI middleware, e.g. GZip.

        Inserted between CORS and logging, matching where the services that use
        one put it today.
        """
        self._extra_middleware.append((middleware_class, options))
        return self

    def with_http_middleware(self, *dispatch: HTTPMiddleware) -> Self:
        """Service-specific ``(request, call_next)`` middleware.

        Registered outside the metrics layer and inside host validation, in call
        order — so the first argument ends up innermost, which is how the gateway
        stacks its rate-limit/cache layer beneath authentication.
        """
        self._http_middleware.extend(dispatch)
        return self

    def with_exception_handlers(self, registry: ExceptionHandlerRegistry) -> Self:
        """Replace the default error contract wholesale."""
        self._errors = registry
        return self

    def with_tracing(
        self, *, instrument_sqlalchemy: bool = True, instrument_redis: bool = True
    ) -> Self:
        """Narrow the OpenTelemetry instrumentation.

        The gateway and notification-service own no SQLAlchemy engine, so probing
        for one only produces noise.
        """
        self._instrument_sqlalchemy = instrument_sqlalchemy
        self._instrument_redis = instrument_redis
        return self

    def without_host_validation(self) -> Self:
        """Opt out of Host-header validation.

        Only the gateway does: it is the edge, its Host is whatever the browser
        sent, and Traefik has already matched the router rule.
        """
        self._host_validation = False
        return self

    def without_request_metrics(self) -> Self:
        """Opt out of the shared latency histogram.

        For a service that records its own — the gateway's ``gateway_requests_total``
        and ``gateway_request_duration_seconds`` already cover every proxied call.
        """
        self._request_metrics = False
        return self

    def without_instrumentator(self) -> Self:
        """Opt out of ``prometheus_fastapi_instrumentator``'s ``http_requests_total``."""
        self._instrumentator = False
        return self

    @property
    def errors(self) -> ExceptionHandlerRegistry:
        """Register extra exception renderers before calling ``build``."""
        return self._errors

    @property
    def metrics(self) -> RequestMetricsHelper:
        """This service's latency histogram, for handlers that record their own."""
        return self._metrics

    # -------------------------------- assembly --------------------------------

    def build(self) -> FastAPI:
        if self._lifespan is None or self._resolve is None:
            raise RuntimeError("with_lifespan() must be called before build()")

        app = FastAPI(
            **self._descriptor.openapi_kwargs(),
            lifespan=self._wrap_lifespan(self._lifespan),
        )

        setup_tracing(
            app,
            service_name=self._descriptor.name,
            instrument_sqlalchemy=self._instrument_sqlalchemy,
            instrument_redis=self._instrument_redis,
        )

        self._add_middleware(app)
        self._add_routes(app)
        self._errors.install(app)
        return app

    def _wrap_lifespan(self, factory: LifespanFactory) -> LifespanFactory:
        """Register the latency histogram before the service's own startup runs.

        Each gunicorn worker must build its own histogram *after* the fork, which
        is why this happens in the lifespan rather than at import time.
        """

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            if self._request_metrics:
                self._metrics.initialize()
            async with factory(app):
                yield

        return lifespan

    def _add_middleware(self, app: FastAPI) -> None:
        """Register the middleware stack.

        Starlette runs middleware LAST-ADDED-FIRST, so this block reads
        innermost-to-outermost and produces this execution chain:

            logging → [extra, e.g. GZip] → CORS → host validation
                    → [service http middleware] → metrics → instrumentator → route

        That is the chain the services run today. Host validation must stay
        inside CORS so a rejected Host is still answered with CORS headers, and
        the metrics layers must stay innermost so they time the handler rather
        than the middleware above them. Do not reshuffle this block.
        """
        if self._instrumentator:
            # Supplies http_requests_total / http_request_duration_seconds, which
            # the Grafana RPS and error-rate panels query. Served through our own
            # /metrics route, so no .expose() call.
            Instrumentator().instrument(app)
        if self._request_metrics:
            add_metrics_middleware(
                app,
                metrics=self._metrics,
                internal_access=self._internal_access,
            )
        for dispatch in self._http_middleware:
            app.middleware("http")(dispatch)
        if self._host_validation:
            # The probe and scrape paths are exempt: kubelet sends the pod IP as
            # the Host header, which can never be in ALLOWED_HOSTS, so validating
            # it would fail every liveness check.
            add_host_validation_middleware(
                app,
                settings=self._settings,
                logger=self._logger,
                exempt_paths=MONITORING_PATHS,
            )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self._settings.CORS_ALLOWED_ORIGINS,
            allow_credentials=self._settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=self._settings.CORS_ALLOWED_METHODS,
            allow_headers=self._settings.CORS_ALLOWED_HEADERS,
        )
        for middleware_class, options in self._extra_middleware:
            app.add_middleware(middleware_class, **options)
        add_logging_middleware(app, service_name=self._descriptor.name)

    def _add_routes(self, app: FastAPI) -> None:
        app.include_router(build_metrics_router())
        app.include_router(
            build_health_router(
                service_name=self._descriptor.name,
                resolve=self._resolve,
                probes=self._probes,
            )
        )
        for router, prefix, tags in self._routers:
            app.include_router(router, prefix=prefix, **({"tags": tags} if tags else {}))
