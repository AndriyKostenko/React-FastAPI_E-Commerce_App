"""Backwards-compatible shim.

``RequestMetricsHelper`` moved to ``shared.app.instrumentation``, where the
histogram name is derived from the service name instead of being hardcoded. The
live instance is now owned by ``ServiceAppBuilder``; reach it via
``main.app`` if a handler needs to record its own observation.
"""

from shared.app.instrumentation import RequestMetricsHelper

__all__ = ["RequestMetricsHelper"]
