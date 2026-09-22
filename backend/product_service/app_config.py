"""How product-service fills in the shared application builder."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from resources import get_product_api_resources, logger, product_api_runtime, settings
from shared.app import ServiceDescriptor
from tasks.broker import taskiq_broker

DESCRIPTOR = ServiceDescriptor(
    name="product-service",
    title="product-service",
    # Was "This is a user service for managing products." — half-copied from
    # user-service and served from /docs.
    description=(
        "This is a product service for managing products, categories, reviews"
        " and generated artwork."
    ),
    api_prefix=settings.PRODUCT_SERVICE_URL_API_VERSION,
    host=settings.APP_HOST,
    port=settings.PRODUCT_SERVICE_APP_PORT,
)

# The readiness probes reach the container through the resolver this service
# already exposes for its request-scoped dependencies.
resolve_resources = get_product_api_resources


@asynccontextmanager
async def product_service_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach one lifespan-owned resource container to this app instance."""
    logger.info(f"Server is starting up on {DESCRIPTOR.host}:{DESCRIPTOR.port}...")
    async with product_api_runtime() as resources:
        app.state.resources = resources
        taskiq_started = False
        try:
            # The schema is owned by Alembic, not by this process.
            # create_all cannot alter an existing table, so bootstrapping
            # here would silently leave a database that predates a
            # migration missing its new columns while the service still
            # reported a clean startup.
            logger.info("Product service schema is managed by Alembic migrations.")
            # A taskiq worker process starts its own broker; starting a second
            # one from the API process would consume the same queues twice.
            if not taskiq_broker.is_worker_process:
                taskiq_started = True
                await taskiq_broker.startup()
                logger.info("TaskIQ broker started successfully.")
            logger.info("Server startup complete!")
            yield
        finally:
            try:
                if taskiq_started:
                    await taskiq_broker.shutdown()
            finally:
                del app.state.resources
    logger.warning("Server has shut down !")
