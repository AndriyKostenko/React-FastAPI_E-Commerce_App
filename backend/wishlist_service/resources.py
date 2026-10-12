from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from aiohttp import ClientSession
from starlette.requests import HTTPConnection

from infrastructure.managers.database_session_manager import DatabaseSessionManager
from settings import Settings

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
        pool_size=app_settings.DB_POOL_SIZE,
        max_overflow=app_settings.DB_MAX_OVERFLOW,
        pool_timeout=app_settings.DB_POOL_TIMEOUT_SECONDS,
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
        # Register the already-open HTTP client first so a failure while
        # starting the database still closes its connector.
        await stack.enter_async_context(resources.http_client)
        await stack.enter_async_context(resources.database)
        yield resources


def get_wishlist_api_resources(connection: HTTPConnection) -> WishlistApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, WishlistApiResources):
        raise RuntimeError("Wishlist API resources are not initialized")
    return resources
