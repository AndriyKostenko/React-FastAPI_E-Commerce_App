"""Liveness and readiness, with each service declaring its own dependencies.

Liveness answers "is this process alive"; readiness answers "should traffic be
routed here".  Conflating them — which the single unconditional ``/health`` did —
makes Kubernetes restart a pod whose Redis merely blipped, instead of draining it.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


class ReadinessProbe[ResourcesT](Protocol):
    """One dependency whose health gates traffic.

    Returns ``False`` — or raises — when the dependency is not usable.
    """

    async def __call__(self, resources: ResourcesT) -> bool: ...


class DatabaseEngineProbe[ResourcesT]:
    """Not ready until the async engine has been created by the lifespan."""

    async def __call__(self, resources: ResourcesT) -> bool:
        return resources.database.async_engine is not None


class RedisPingProbe[ResourcesT]:
    """PINGs one named Redis-backed manager on the resource container.

    The attribute is named rather than the client passed in, because the
    container is only built once the lifespan opens — long after the probe list
    is declared at import time.
    """

    def __init__(self, attribute: str) -> None:
        self._attribute = attribute

    async def __call__(self, resources: ResourcesT) -> bool:
        await getattr(resources, self._attribute).redis.ping()
        return True


def build_health_router[ResourcesT](
    *,
    service_name: str,
    resolve: Callable[[Request], ResourcesT],
    probes: Sequence[ReadinessProbe[ResourcesT]],
) -> APIRouter:
    """Build ``/health/live``, ``/health/ready`` and the legacy ``/health``."""
    router = APIRouter(tags=["Health Check"])

    @router.get("/health/live")
    async def health_live() -> JSONResponse:
        """Liveness only: the process can answer requests."""
        return JSONResponse(
            content={
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": service_name,
            },
            status_code=200,
            headers={"Cache-Control": "no-cache"},
        )

    @router.get("/health/ready")
    async def health_ready(request: Request) -> JSONResponse:
        """Readiness: every declared dependency answers."""
        try:
            resources = resolve(request)
            for probe in probes:
                if not await probe(resources):
                    return JSONResponse(status_code=503, content={"status": "not_ready"})
        except Exception:
            # A probe that raises (Redis timeout, exhausted pool, resources not
            # yet attached) is a not-ready signal, never a 500 — the orchestrator
            # must stop routing to this pod, not tear it down.
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    # Back-compat: existing probes and compose healthchecks still hit /health.
    router.add_api_route("/health", health_live, include_in_schema=False)
    return router
