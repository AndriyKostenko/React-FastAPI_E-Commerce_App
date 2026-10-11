"""The Prometheus scrape endpoint, multiprocess-aware."""

import os

from fastapi import APIRouter
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest, multiprocess
from starlette.responses import Response as PlainResponse


def build_metrics_router() -> APIRouter:
    router = APIRouter()

    @router.get("/metrics", include_in_schema=False)
    def metrics() -> PlainResponse:
        """Multiprocess-aware Prometheus metrics endpoint."""
        multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

        if multiproc_dir:
            # Multi-worker: merge all worker .db files from the shared dir.
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
        else:
            # Single process (local dev): use the default registry directly.
            registry = REGISTRY

        return PlainResponse(
            content=generate_latest(registry),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return router
