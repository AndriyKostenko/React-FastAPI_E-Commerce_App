"""How user-service fills in the shared application builder.

Everything here is specific to this service: who it is, and how its resource
container is opened and resolved.  The generic assembly lives in ``shared.app``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from managers import SERVICE_NAME, ResourceManager, UserApiResources, logger, settings
from shared.app import ServiceDescriptor

DESCRIPTOR = ServiceDescriptor(
    name=SERVICE_NAME,
    title="user-service",
    description=(
        "This is a user service for managing users, authentication, and authorization."
    ),
    api_prefix=settings.USER_SERVICE_URL_API_VERSION,
    host=settings.APP_HOST,
    port=settings.USER_SERVICE_APP_PORT,
)


@asynccontextmanager
async def user_service_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach one lifespan-owned resource container to this app instance."""
    logger.info(f"Server is starting up on {DESCRIPTOR.host}:{DESCRIPTOR.port}...")
    async with ResourceManager() as resources:
        # Register resources in app state for request-scoped dependencies.
        ResourceManager.attach(app, resources)
        try:
            # The schema is owned by Alembic, not by this process.
            # create_all cannot alter an existing table, so bootstrapping
            # here would silently leave a database that predates a
            # migration missing its new columns while the service still
            # reported a clean startup.
            logger.info("User service schema is managed by Alembic migrations.")
            logger.info("User service API resources are initialized.")
            logger.info("Server startup complete!")
            yield
        finally:
            ResourceManager.detach(app)
    logger.warning("Server has shut down!")


def resolve_resources(request: Request) -> UserApiResources:
    """Reach the lifespan-owned container from a request — used by the probes."""
    return ResourceManager.resolve(request)
