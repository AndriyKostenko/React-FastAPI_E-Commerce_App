from prometheus_client import Histogram


class RequestMetricsHelper:
    """Prometheus histogram helper for HTTP request latency."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def initialize(self):
        if self._initialized:
            return
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds_shipping",
            "HTTP request latency for shipping service",
            ["method", "endpoint", "status_code"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        self._initialized = True

    def observe(self, request, response, duration: float) -> None:
        if not self._initialized:
            self.initialize()
        endpoint = request.url.path
        self.http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=str(response.status_code),
        ).observe(duration)


request_metrics_helper = RequestMetricsHelper()
