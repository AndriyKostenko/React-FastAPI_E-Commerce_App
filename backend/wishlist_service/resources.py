from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from aiohttp import ClientSession
from starlette.requests import HTTPConnection

from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class WishlistApiResources:
    """Long-lived resources owned by one wishlist API process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    http_client: ClientSession


def create_wishlist_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> WishlistApiResources:
    """Build a fresh resource graph for one FastAPI lifespan."""
    database = DatabaseSessionManager(
        database_url=app_settings.WISHLIST_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )
    return WishlistApiResources(
        settings=app_settings,
        logger=app_logger,
        database=database,
        http_client=ClientSession(),
    )


@asynccontextmanager
async def wishlist_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[WishlistApiResources]:
    """Start and reliably stop resources owned by one wishlist API process."""
    resources = create_wishlist_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.http_client)
        yield resources


def get_wishlist_api_resources(connection: HTTPConnection) -> WishlistApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, WishlistApiResources):
        raise RuntimeError("Wishlist API resources are not initialized")
    return resources
