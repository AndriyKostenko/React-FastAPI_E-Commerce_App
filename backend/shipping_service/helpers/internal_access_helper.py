"""Backwards-compatible shim.

The implementation moved to ``infrastructure.app.instrumentation`` so every service
shares one definition of which paths are monitoring rather than client traffic.
"""

from infrastructure.app.instrumentation import InternalAccessHelper, internal_access_helper

__all__ = ["InternalAccessHelper", "internal_access_helper"]
