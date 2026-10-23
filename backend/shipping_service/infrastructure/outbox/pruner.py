"""Deletes outbox events long after they were published.

A published event's payload is a copy of what the service sent: an order with
the customer's email address, a shipping address, a reset link. Once it has
been relayed, the row is only history, so it is kept ``OUTBOX_RETENTION_DAYS``
for tracing a problem and then deleted. Unpublished events are never touched:
they are still owed to the broker.
"""

from datetime import datetime, timedelta, timezone
from logging import Logger
from time import monotonic

from sqlalchemy.orm import DeclarativeBase

from infrastructure.database_layer.outbox_repository import OutboxRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager

OUTBOX_RETENTION_DAYS = 30


class OutboxPruner:
    """Removes a service's published outbox events once they are older than the retention period."""

    def __init__(
        self,
        session_manager: DatabaseSessionManager,
        outbox_model: type[DeclarativeBase],
        logger: Logger,
        retention_days: int = OUTBOX_RETENTION_DAYS,
        batch_size: int = 1000,
        interval_seconds: float = 3600.0,
    ) -> None:
        self.session_manager = session_manager
        self.outbox_model = outbox_model
        self.logger = logger
        self.retention_days = retention_days
        self.batch_size = batch_size
        self.interval_seconds = interval_seconds
        # Monotonic time of the next run: due at once when the worker starts.
        self._next_run_at = 0.0

    async def prune(self, now: datetime | None = None) -> int:
        """Delete every event published before the retention cutoff; how many went."""
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=self.retention_days)
        deleted = 0
        while True:
            # One short transaction per batch, so a large backlog never holds
            # a long lock on the table the relay is polling.
            async with self.session_manager.transaction() as session:
                repository = OutboxRepository(session=session, model=self.outbox_model)
                count = await repository.delete_processed_before(cutoff, limit=self.batch_size)
            deleted += count
            if count < self.batch_size:
                break
        if deleted:
            self.logger.info("Deleted %s outbox events published before %s", deleted, cutoff.date())
        return deleted

    async def prune_if_due(self) -> None:
        """Prune at most once per interval; a failure is logged and retried next interval."""
        if monotonic() < self._next_run_at:
            return
        self._next_run_at = monotonic() + self.interval_seconds
        try:
            await self.prune()
        except Exception:
            self.logger.exception("Outbox prune failed")
