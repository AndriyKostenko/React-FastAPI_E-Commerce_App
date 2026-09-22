"""Backwards-compatible shim.

The implementation moved to ``shared.app.instrumentation`` so all services share
one copy. Kept so existing imports (``from helpers.internal_access_helper import
internal_access_helper``) keep resolving.
"""

from shared.app.instrumentation import InternalAccessHelper, internal_access_helper

__all__ = ["InternalAccessHelper", "internal_access_helper"]
