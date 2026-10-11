"""Backwards-compatible shim.

``RequestMetricsHelper`` moved to ``infrastructure.app.instrumentation``, where the
histogram name is derived from the service name instead of being hardcoded to
user-service's. The live instance is owned by ``ServiceAppBuilder``.
"""

from infrastructure.app.instrumentation import RequestMetricsHelper

__all__ = ["RequestMetricsHelper"]
