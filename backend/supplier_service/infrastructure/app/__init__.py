"""Shared assembly of a service's FastAPI application.

The wiring every ``main.py`` repeated — middleware order, health probes, the
Prometheus endpoint and the exception contract — lives here, so a service's own
``main.py`` is left stating only what is specific to it.
"""

from infrastructure.app.builder import ServiceAppBuilder
from infrastructure.app.descriptor import ServiceDescriptor
from infrastructure.app.errors import ExceptionHandlerRegistry, ExceptionRenderer, utc_timestamp
from infrastructure.app.health import (
    DatabaseEngineProbe,
    ReadinessProbe,
    RedisPingProbe,
    build_health_router,
)
from infrastructure.app.instrumentation import (
    MONITORING_PATHS,
    InternalAccessHelper,
    RequestMetricsHelper,
    internal_access_helper,
)
from infrastructure.app.metrics import build_metrics_router

__all__ = [
    "DatabaseEngineProbe",
    "ExceptionHandlerRegistry",
    "ExceptionRenderer",
    "MONITORING_PATHS",
    "InternalAccessHelper",
    "ReadinessProbe",
    "RedisPingProbe",
    "RequestMetricsHelper",
    "ServiceAppBuilder",
    "ServiceDescriptor",
    "build_health_router",
    "build_metrics_router",
    "internal_access_helper",
    "utc_timestamp",
]
