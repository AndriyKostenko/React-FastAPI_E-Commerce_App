"""Backwards-compatible shim.

``RequestMetricsHelper`` moved to ``shared.app.instrumentation``, where the
histogram name is derived from the service name instead of being hardcoded to
user-service's. The live instance is owned by ``ServiceAppBuilder``.
"""

from shared.app.instrumentation import RequestMetricsHelper

__all__ = ["RequestMetricsHelper"]
