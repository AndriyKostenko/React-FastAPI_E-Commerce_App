from fastapi import Request, Response
from prometheus_client import Histogram


class RequestMetricsHelper:
    """Encapsulates request latency metric setup and recording."""
    def __init__(self) -> None:
        self._request_latency: Histogram | None = None

    def initialize(self) -> None:
        self._request_latency = Histogram(
            "notification_service_request_latency_seconds",
            "HTTP request latency histogram (multiprocess-safe)",
            ["method", "handler", "status"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
        )

    def observe(self, request: Request, response: Response, duration: float) -> None:
        if self._request_latency is None:
            return

        route = request.scope.get("route")
        handler = route.path if route else request.url.path
        self._request_latency.labels(
            method=request.method,
            handler=handler,
            status=f"{response.status_code // 100}xx",
        ).observe(duration)


request_metrics_helper = RequestMetricsHelper()
