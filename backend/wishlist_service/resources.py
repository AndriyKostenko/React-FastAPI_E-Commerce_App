from dataclasses import dataclass
from logging import Logger

from aiohttp import ClientSession

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


def create_wishlist_api_resources() -> WishlistApiResources:
    """Build a fresh resource graph for one FastAPI lifespan."""
    database = DatabaseSessionManager(
        database_url=settings.WISHLIST_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )
    return WishlistApiResources(
        settings=settings,
        logger=logger,
        database=database,
        http_client=ClientSession(),
    )
