from datetime import datetime, timedelta, timezone
from logging import Logger

from database_layer.notification_repository import NotificationRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager


class NotificationRetention:
    """Deletes notifications once they are older than the retention period (the privacy policy's)."""

    def __init__(
        self,
        database: DatabaseSessionManager,
        logger: Logger,
        retention_days: int,
        batch_size: int = 1000,
    ) -> None:
        self._database = database
        self._logger = logger
        self._retention_days = retention_days
        self._batch_size = batch_size

    async def prune(self, now: datetime | None = None) -> int:
        """Delete every notification created before the cutoff; how many went."""
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=self._retention_days)
        deleted = 0
        while True:
            # One short transaction per batch, so the API's reads never wait long.
            async with self._database.transaction() as session:
                count = await NotificationRepository(session).delete_created_before(cutoff, self._batch_size)
            deleted += count
            if count < self._batch_size:
                break
        self._logger.info("Deleted %s notifications created before %s", deleted, cutoff.date())
        return deleted
