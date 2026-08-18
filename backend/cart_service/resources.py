from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from starlette.requests import HTTPConnection
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class CartApiResources:
    """Long-lived resources owned by one cart API process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager


def create_cart_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> CartApiResources:
    """Build a fresh resource graph for one FastAPI lifespan."""
    database = DatabaseSessionManager(
        database_url=app_settings.CART_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )
    return CartApiResources(
        settings=app_settings,
        logger=app_logger,
        database=database,
    )


@asynccontextmanager
async def cart_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[CartApiResources]:
    """Start and reliably stop resources owned by one cart API process."""
    resources = create_cart_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        stack.push_async_callback(resources.database.close)
        yield resources


def get_cart_api_resources(connection: HTTPConnection) -> CartApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, CartApiResources):
        raise RuntimeError("Cart API resources are not initialized")
    return resources
