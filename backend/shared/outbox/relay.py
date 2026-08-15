"""Service-agnostic transactional outbox relay.

Each business service owns its table and event-routing function.  This module
owns the otherwise identical polling, row locking, retry loop, and lifecycle.
It is intended to run in a dedicated worker process, never in an ASGI worker.
"""

from asyncio import Event, TimeoutError, wait_for
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Any
from sqlalchemy.orm import DeclarativeBase

from shared.database_layer.outbox_repository import OutboxRepository
from shared.managers.database_session_manager import DatabaseSessionManager


EventRouter = Callable[[str, dict[str, Any]], Awaitable[None]]


class OutboxRelay:
    """Poll one service-owned outbox and publish its events at least once."""

    def __init__(
        self,
        session_manager: DatabaseSessionManager,
        event_router: EventRouter,
        logger: Logger,
        poll_interval: float,
        outbox_model: type[DeclarativeBase],
        batch_size: int = 50,
        base_retry_seconds: float = 5.0,
        max_retry_seconds: float = 300.0,
    ) -> None:
        self.session_manager = session_manager
        self.event_router = event_router
        self.logger = logger
        self.poll_interval = poll_interval
        self.outbox_model = outbox_model
        self.batch_size = batch_size
        self.base_retry_seconds = base_retry_seconds
        self.max_retry_seconds = max_retry_seconds

    async def relay_once(self) -> int:
        """Publish one locked batch and return its number of successful events.

        A publish can succeed just before the worker dies, so consumers must
        deduplicate on ``event_id``.  Marking a record only after publishing is
        intentional: it provides at-least-once delivery rather than data loss.
        """
        published = 0
        async with self.session_manager.transaction() as session:
            repository = OutboxRepository(session=session, model=self.outbox_model)
            events = await repository.get_pending_with_lock(limit=self.batch_size)
            for event in events:
                try:
                    await self.event_router(event.event_type, event.payload)
                    await repository.update_by_id(
                        item_id=event.id,
                        data={
                            "processed": True,
                            "processed_at": datetime.now(timezone.utc),
                            "last_error": None,
                            "next_retry_at": None,
                        },
                    )
                    published += 1
                except Exception as exc:
                    attempts = int(event.attempts or 0) + 1
                    retry_seconds = min(
                        self.base_retry_seconds * (2 ** min(attempts - 1, 16)),
                        self.max_retry_seconds,
                    )
                    await repository.update_by_id(
                        item_id=event.id,
                        data={
                            "attempts": attempts,
                            "last_error": str(exc)[:2000],
                            "next_retry_at": datetime.now(timezone.utc)
                            + timedelta(seconds=retry_seconds),
                        },
                    )
                    self.logger.exception("Outbox publish failed for event %s", event.id)
        return published

    async def run(self, stop_event: Event) -> None:
        """Run until signalled, waking immediately during graceful shutdown."""
        while not stop_event.is_set():
            try:
                await self.relay_once()
            except Exception:
                self.logger.exception("Outbox relay batch failed")
            try:
                await wait_for(stop_event.wait(), timeout=self.poll_interval)
            except TimeoutError:
                pass
