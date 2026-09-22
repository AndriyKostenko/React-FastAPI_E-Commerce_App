"""Per-request instrumentation shared by every service.

Both helpers used to be copy-pasted into each service's ``helpers/`` package,
which is why the latency histogram was hardcoded to
``user_service_request_latency_seconds`` in all ten copies.  Here the metric name
is derived from the service name instead.
"""

from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import Histogram
from starlette.responses import Response as StarletteResponse

MONITORING_PATHS: tuple[str, ...] = ("/health", "/health/live", "/health/ready", "/metrics")
"""Paths an orchestrator and Prometheus reach us on, rather than a client.

They are exempt from Host validation, because kubelet sends the pod IP as the
Host header and that can never be in ``ALLOWED_HOSTS``; and they are excluded
from the latency histogram, because probe traffic would otherwise dominate it.
"""


class InternalAccessHelper:
    """Encapsulates internal monitoring path and network checks."""

    def __init__(self, internal_paths: tuple[str, ...] = MONITORING_PATHS) -> None:
        self._internal_paths = frozenset(internal_paths)
        self._private_prefixes = ("10.", "172.", "192.168.")

    def is_internal_path(self, path: str) -> bool:
        return path in self._internal_paths

    def is_internal_client(self, request: Request) -> bool:
        client_host = request.client.host if request.client else ""
        return self.is_internal_path(request.url.path) or any(
            client_host.startswith(prefix) for prefix in self._private_prefixes
        )


class RequestMetricsHelper:
    """Encapsulates request latency metric setup and recording.

    One instance per service process.  The histogram is deliberately *not* built
    in ``__init__``: under gunicorn each worker must create its own after the
    fork so multiprocess mode can merge the shared ``PROMETHEUS_MULTIPROC_DIR``
    files correctly.
    """

    def __init__(self, service_name: str) -> None:
        # "user-service" is not a legal Prometheus metric name component.
        self._metric_prefix = service_name.replace("-", "_")
        self._request_latency: Histogram | None = None

    def initialize(self) -> None:
        # Called once per worker, from the lifespan. Guarded because registering
        # the same timeseries twice raises out of prometheus_client, which would
        # turn a double lifespan (reload, a test that re-enters it) into a crash.
        if self._request_latency is not None:
            return
        self._request_latency = Histogram(
            f"{self._metric_prefix}_request_latency_seconds",
            "HTTP request latency histogram (multiprocess-safe)",
            ["method", "handler", "status"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        )

    def observe(self, request: Request, response: Response, duration: float) -> None:
        if self._request_latency is None:
            return

        # Prefer the route template ("/users/{user_id}") over the raw path, or the
        # label cardinality grows with the number of distinct ids ever requested.
        route = request.scope.get("route")
        handler = route.path if route else request.url.path
        self._request_latency.labels(
            method=request.method,
            handler=handler,
            status=f"{response.status_code // 100}xx",
        ).observe(duration)


def add_metrics_middleware(
    app: FastAPI,
    *,
    metrics: RequestMetricsHelper,
    internal_access: InternalAccessHelper,
) -> None:
    """Register the single custom instrumentation path; avoids double-counting."""

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next) -> StarletteResponse:
        """Records request latency into a multiprocess-safe histogram."""
        # Skip internal paths — no value in tracking /metrics scraping itself.
        if internal_access.is_internal_path(request.url.path):
            return await call_next(request)
        start = perf_counter()
        response = await call_next(request)
        metrics.observe(request=request, response=response, duration=perf_counter() - start)
        return response


internal_access_helper = InternalAccessHelper()
"""Process-wide default: stateless, so one instance is safe to share."""
