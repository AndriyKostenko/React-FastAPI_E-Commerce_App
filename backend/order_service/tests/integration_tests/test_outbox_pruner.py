"""
OutboxPruner against the real order test database (the relay and pruner are
the same copy in every service with an outbox; ci/check_copies.py holds them
equal). Rows are written with past processed_at times; nothing is faked.

Rules: a published event is deleted OUTBOX_RETENTION_DAYS after it was
published; one not yet published is never deleted, however old; a backlog
bigger than a batch goes in one run; the relay prunes at most once an interval.
"""

from asyncio import Event, create_task, sleep
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID

import pytest
from sqlalchemy import select

from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from infrastructure.outbox import OUTBOX_RETENTION_DAYS, OutboxPruner, OutboxRelay
from models.base import Base
from models.outbox_models import OutboxEvent

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.recreate_schema(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _event(db: TestDatabaseSessionManager, published_days_ago: float | None, made_days_ago: float = 0) -> UUID:
    """An outbox row carrying a customer's address; published that many days ago, or never."""
    async with db.transaction() as session:
        event = OutboxEvent(
            event_type="order.confirmed",
            payload={"user_email": "customer@example.com"},
            processed=published_days_ago is not None,
            processed_at=None if published_days_ago is None else NOW - timedelta(days=published_days_ago),
            date_created=NOW - timedelta(days=max(made_days_ago, published_days_ago or 0)),
        )
        session.add(event)
        await session.flush()
        return event.id


async def _ids(db: TestDatabaseSessionManager) -> set[UUID]:
    async with db.transaction() as session:
        return set((await session.execute(select(OutboxEvent.id))).scalars())


def _pruner(db: TestDatabaseSessionManager, **options) -> OutboxPruner:
    return OutboxPruner(db, OutboxEvent, getLogger("test"), **options)


async def test_a_published_event_goes_after_the_retention_period(db) -> None:
    await _event(db, published_days_ago=OUTBOX_RETENTION_DAYS + 1)
    recent = await _event(db, published_days_ago=OUTBOX_RETENTION_DAYS - 1)

    assert await _pruner(db).prune(now=NOW) == 1
    assert await _ids(db) == {recent}


async def test_an_unpublished_event_is_never_deleted_however_old(db) -> None:
    owed = await _event(db, published_days_ago=None, made_days_ago=400)

    assert await _pruner(db).prune(now=NOW) == 0
    assert await _ids(db) == {owed}


async def test_a_backlog_bigger_than_a_batch_goes_in_one_run(db) -> None:
    for _ in range(5):
        await _event(db, published_days_ago=90)

    assert await _pruner(db, batch_size=2).prune(now=NOW) == 5
    assert await _ids(db) == set()


async def test_the_relay_prunes_at_most_once_an_interval(db) -> None:
    pruner = _pruner(db, interval_seconds=3600)
    await _event(db, published_days_ago=90)
    await pruner.prune_if_due()  # due at once when the worker starts
    assert await _ids(db) == set()

    again = await _event(db, published_days_ago=90)
    await pruner.prune_if_due()  # within the hour: not yet
    assert await _ids(db) == {again}


async def test_the_running_relay_prunes_what_it_published_long_ago(db) -> None:
    """The worker process is the relay's loop; nothing else calls the pruner."""
    await _event(db, published_days_ago=OUTBOX_RETENTION_DAYS + 1)

    async def publish(event_type: str, payload: dict) -> None:
        return None

    stop = Event()
    relay = OutboxRelay(db, publish, getLogger("test"), poll_interval=0.05, outbox_model=OutboxEvent)
    running = create_task(relay.run(stop))
    await sleep(0.3)
    stop.set()
    await running

    assert await _ids(db) == set()

