"""Removes customer details from CJ orders that ended long enough ago, once a day."""

from resources import create_database_manager, logger, settings
from service_layer.cj_order_personal_data_retention import CJOrderPersonalDataRetention
from tasks.broker import taskiq_broker


async def run_cj_order_retention() -> int:
    """One run, with a database engine of its own."""
    database = create_database_manager()
    try:
        return await CJOrderPersonalDataRetention(
            database=database, logger=logger, retention_days=settings.CJ_ORDER_PERSONAL_DATA_RETENTION_DAYS
        ).prune()
    finally:
        await database.close()


@taskiq_broker.task(schedule=[{"cron": "30 3 * * *"}])
async def remove_ended_cj_order_personal_data() -> dict[str, int]:
    return {"orders": await run_cj_order_retention()}
