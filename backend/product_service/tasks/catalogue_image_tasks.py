"""Copies CJ catalogue images into the catalogue object store.

See CatalogueImageMirrorService. A sweep costs one query when nothing is
pending, so it runs often: a product the 10-minute supplier sync brings in
is served from our own storage within the quarter hour.
"""

from datetime import UTC, datetime

from aiohttp import ClientSession

from resources import create_cache_manager, create_database_manager, logger, settings
from service_layer.catalogue_image_fetcher import CatalogueImageFetcher
from service_layer.catalogue_image_mirror_service import CatalogueImageMirrorService, MirrorReport
from storage.object_storage_provider import get_object_storage_provider
from tasks.broker import taskiq_broker


async def run_catalogue_image_mirror() -> MirrorReport:
    """One sweep, with its own database, cache and HTTP resources."""
    database = create_database_manager()
    cache = create_cache_manager()
    try:
        await cache.connect()
        async with ClientSession() as http:
            return await CatalogueImageMirrorService(
                database=database,
                store=get_object_storage_provider().catalogue(),
                fetcher=CatalogueImageFetcher(http, max_bytes=settings.CATALOGUE_IMAGE_MAX_BYTES),
                cache_manager=cache,
                settings=settings,
                logger=logger,
            ).mirror_pending()
    finally:
        try:
            await cache.close()
        finally:
            await database.close()


@taskiq_broker.task(schedule=[{"cron": "*/15 * * * *"}])
async def mirror_catalogue_images() -> dict[str, int | bool | str]:
    """A run still going when the next one fires is not doubled: the sweep
    holds a database lock, and a second run returns at once."""
    report = await run_catalogue_image_mirror()
    return {"run_at": datetime.now(UTC).isoformat(), **report.as_dict()}
