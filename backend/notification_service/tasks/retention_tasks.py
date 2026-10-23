"""Deletes notifications older than NOTIFICATION_RETENTION_DAYS, once a day."""

from resources import create_database_manager, logger, settings
from service_layer.notification_retention import NotificationRetention
from tasks.broker import taskiq_broker


async def run_notification_retention() -> int:
    """One run, with a database engine of its own."""
    database = create_database_manager()
    try:
        return await NotificationRetention(
            database=database, logger=logger, retention_days=settings.NOTIFICATION_RETENTION_DAYS
        ).prune()
    finally:
        await database.close()


@taskiq_broker.task(schedule=[{"cron": "40 3 * * *"}])
async def delete_old_notifications() -> dict[str, int]:
    return {"deleted": await run_notification_retention()}
