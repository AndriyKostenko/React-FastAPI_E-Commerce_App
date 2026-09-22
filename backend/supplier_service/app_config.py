"""How supplier-service fills in the shared application builder."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from resources import get_supplier_api_resources, logger, settings, supplier_api_runtime
from service_layer.cj_api_client import CJDropshippingAPIError
from shared.app import ExceptionHandlerRegistry, ServiceDescriptor, utc_timestamp
from utils.seed_database import seed_default_supplier_config

DESCRIPTOR = ServiceDescriptor(
    name="supplier-service",
    title="supplier-service",
    description=(
        "Supplier integration service for fetching products and emitting import events."
    ),
    api_prefix=settings.SUPPLIER_SERVICE_URL_API_VERSION,
    host=settings.APP_HOST,
    port=settings.SUPPLIER_SERVICE_APP_PORT,
    version="0.1.0",
)

# The readiness probes reach the container through the resolver this service
# already exposes for its request-scoped dependencies.
resolve_resources = get_supplier_api_resources


@asynccontextmanager
async def supplier_service_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach one lifespan-owned resource container to this app instance."""
    logger.info(f"Server is starting up on {DESCRIPTOR.host}:{DESCRIPTOR.port}...")
    async with supplier_api_runtime() as resources:
        app.state.resources = resources
        try:
            # The schema is owned by Alembic, not by this process.
            # create_all cannot alter an existing table, so bootstrapping
            # here would silently leave a database that predates a
            # migration missing its new columns while the service still
            # reported a clean startup.
            logger.info("Supplier service schema is managed by Alembic migrations.")
            # Row-level defaults are seeded here rather than in a migration so a
            # fresh database is usable without a manual step.
            async with resources.database.transaction() as session:
                await seed_default_supplier_config(
                    session=session,
                    settings=resources.settings,
                )
                logger.info("Default supplier config seeded.")
            logger.info("Supplier service startup complete!")
            yield
        finally:
            del app.state.resources
    logger.warning("Supplier service has shut down!")


def _cj_api_error(request: Request, exc: CJDropshippingAPIError) -> JSONResponse:
    """CJ is upstream of us, so its failures are a bad gateway, not our 500."""
    return JSONResponse(
        status_code=502,
        content={
            "detail": str(exc),
            "timestamp": utc_timestamp(),
            "path": request.url.path,
        },
    )


def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log the traceback, tell the client nothing about it."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "timestamp": utc_timestamp(),
            "path": request.url.path,
        },
    )


def build_exception_handlers() -> ExceptionHandlerRegistry:
    """The shared contract plus the two this service adds."""
    return (
        ExceptionHandlerRegistry()
        .register(CJDropshippingAPIError, _cj_api_error)
        .register(Exception, _unhandled_error)
    )
