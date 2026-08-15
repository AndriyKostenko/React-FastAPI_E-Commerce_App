from dataclasses import dataclass
from logging import Logger

from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class CartApiResources:
    """Long-lived resources owned by one cart API process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager


def create_cart_api_resources() -> CartApiResources:
    """Build a fresh resource graph for one FastAPI lifespan."""
    database = DatabaseSessionManager(
        database_url=settings.CART_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )
    return CartApiResources(
        settings=settings,
        logger=logger,
        database=database,
    )
