"""How shipping-service fills in the shared application builder.

Everything here is specific to this service: who it is, and how its resource
container is opened.  The generic assembly lives in ``shared.app``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from resources import shipping_api_runtime, get_shipping_api_resources
from service_config import logger, settings
from shared.app import ServiceDescriptor

DESCRIPTOR = ServiceDescriptor(
    name="shipping-service",
    title="shipping-service",
    description=(
        "This is a shipping service for managing shipping methods and shipments."
    ),
    api_prefix=settings.SHIPPING_SERVICE_URL_API_VERSION,
    host=settings.APP_HOST,
    port=settings.SHIPPING_SERVICE_APP_PORT,
    version="0.0.1",
)

# The readiness probes reach the container through the resolver this service
# already exposes for its request-scoped dependencies.
resolve_resources = get_shipping_api_resources


@asynccontextmanager
async def shipping_service_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach one lifespan-owned resource container to this app instance."""
    logger.info(f"Server is starting up on {DESCRIPTOR.host}:{DESCRIPTOR.port}...")
    async with shipping_api_runtime() as resources:
        app.state.resources = resources
        try:
            # The schema is owned by Alembic, not by this process.
            # create_all cannot alter an existing table, so bootstrapping
            # here would silently leave a database that predates a
            # migration missing its new columns while the service still
            # reported a clean startup.
            logger.info("Shipping service schema is managed by Alembic migrations.")
            logger.info("Shipping event publisher started.")
            logger.info("Server startup complete!")
            yield
        finally:
            del app.state.resources
    logger.warning("Server has shut down!")
