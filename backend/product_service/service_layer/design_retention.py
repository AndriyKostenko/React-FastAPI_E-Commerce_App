"""
How long product-service keeps what customers made: designs nobody ordered,
and the record of refused ones (the privacy policy: no longer than needed).

A design an order holds (``retained_artwork``) is never deleted here: it is
part of the order record. The sweeps run daily (tasks/retention_tasks.py);
a deleted account's unordered designs and its id on refusals go at once
(the user.deleted consumer).
"""

from datetime import datetime, timedelta, timezone
from logging import Logger
from uuid import UUID

from database_layer.design_moderation_refusal_repository import DesignModerationRefusalRepository
from database_layer.generated_design_repository import GeneratedDesignRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager
from storage.object_store import ObjectStore


class DesignRetention:
    """Deletes stored designs that no order holds: once they are old enough, or when their owner leaves."""

    def __init__(
        self,
        database: DatabaseSessionManager,
        store: ObjectStore,
        logger: Logger,
        retention_days: int,
        batch_size: int = 100,
    ) -> None:
        self._database = database
        self._store = store
        self._logger = logger
        self._retention_days = retention_days
        self._batch_size = batch_size

    async def prune(self, now: datetime | None = None) -> int:
        """Delete every unordered design made before the cutoff; how many went."""
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=self._retention_days)
        deleted = await self._delete_unordered(made_before=cutoff)
        self._logger.info("Deleted %s unordered designs made before %s", deleted, cutoff.date())
        return deleted

    async def forget_user(self, user_id: UUID) -> int:
        """Delete every unordered design of a deleted account, whatever its age."""
        return await self._delete_unordered(user_id=user_id)

    async def _delete_unordered(self, made_before: datetime | None = None, user_id: UUID | None = None) -> int:
        deleted = 0
        while True:
            async with self._database.transaction() as session:
                designs = await GeneratedDesignRepository(session).unordered(
                    limit=self._batch_size, made_before=made_before, user_id=user_id
                )
            if not designs:
                return deleted
            # The object first: a row whose object is gone is only retried
            # next run, while an object whose row is gone could never be found
            # again. No order can claim these in between: checkout refuses a
            # design past its orderable age, and a deleted account cannot order.
            for design in designs:
                await self._store.delete(design.key)
            async with self._database.transaction() as session:
                await GeneratedDesignRepository(session).forget([design.key for design in designs])
            deleted += len(designs)
            if len(designs) < self._batch_size:
                return deleted


class DesignRefusalRetention:
    """Deletes refusal records once they are old enough; drops a deleted account's id from them."""

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
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=self._retention_days)
        deleted = 0
        while True:
            async with self._database.transaction() as session:
                count = await DesignModerationRefusalRepository(session).delete_created_before(
                    cutoff, self._batch_size
                )
            deleted += count
            if count < self._batch_size:
                break
        self._logger.info("Deleted %s design refusals recorded before %s", deleted, cutoff.date())
        return deleted

    async def forget_user(self, user_id: UUID) -> int:
        async with self._database.transaction() as session:
            return await DesignModerationRefusalRepository(session).forget_user(user_id)
