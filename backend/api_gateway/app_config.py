"""How api-gateway fills in the shared application builder.

The gateway is the edge, not a CRUD service, so it differs from the other nine
in three ways that are stated explicitly in ``main.py`` rather than by omission:
it validates no Host header (Traefik has already matched the router rule and the
browser's Host is whatever the deployment answers to), it records its own
request counters instead of the shared latency histogram, and it renders only
its own ``BaseAPIException`` — a validation error belongs to the upstream service
that produced it and is proxied through untouched.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram

from resources import api_gateway_runtime, get_api_gateway_resources, logger, settings
from shared.app import MONITORING_PATHS, ExceptionHandlerRegistry, ServiceDescriptor
from shared.exceptions.base_exceptions import BaseAPIException
from shared.app.errors import api_exception_renderer

DESCRIPTOR = ServiceDescriptor(
    name="api-gateway",
    title="API Gateway",
    description=(
        "The single entry point the frontend calls: authenticates requests, applies"
        " rate limits and response caching, and proxies to every backing service."
    ),
    api_prefix=settings.API_GATEWAY_SERVICE_URL_API_VERSION,
    host=settings.APP_HOST,
    port=settings.API_GATEWAY_SERVICE_APP_PORT,
    version="0.1.0",
)

# The readiness probes reach the container through the resolver this service
# already exposes for its request-scoped dependencies.
resolve_resources = get_api_gateway_resources

# Built during the lifespan, not at import: each gunicorn worker must register
# its own collectors after the fork for multiprocess mode to merge them.
REQUEST_COUNTER: Counter | None = None
LATENCY_COUNTER: Histogram | None = None


@asynccontextmanager
async def api_gateway_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach one lifespan-owned resource container to this app instance."""
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

    logger.info(f"Server is starting up on {DESCRIPTOR.host}:{DESCRIPTOR.port}...")
    async with api_gateway_runtime() as resources:
        app.state.resources = resources
        try:
            logger.info("Server startup complete!")
            yield
        finally:
            del app.state.resources

    logger.warning("Server has shut down !")


async def gateway_middleware(request: Request, call_next):
    """Global rate limiting, response caching, and cache invalidation.

    Monitoring paths bypass all gateway logic — they must never be rate-limited
    or cached.
    """
    if request.url.path in MONITORING_PATHS:
        return await call_next(request)

    resources = get_api_gateway_resources(request)
    is_public = resources.auth.is_public_endpoint(request.url.path, request.method)
    start = perf_counter()
    response = await resources.request_middleware(request, call_next, is_public=is_public)
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


async def authentication_middleware(request: Request, call_next):
    """Authentication middleware to handle JWT tokens."""
    logger.debug("Running authentication middleware...")
    return await get_api_gateway_resources(request).auth.middleware(request, call_next)


def build_exception_handlers() -> ExceptionHandlerRegistry:
    """Only our own API exceptions.

    A ``RequestValidationError`` raised here would be about a proxy route's own
    signature; the upstream service's validation errors arrive as already-rendered
    response bodies and are passed through, so adding the shared validation
    renderers would change what the frontend receives.
    """
    return ExceptionHandlerRegistry(defaults=False).register(
        BaseAPIException, api_exception_renderer
    )
