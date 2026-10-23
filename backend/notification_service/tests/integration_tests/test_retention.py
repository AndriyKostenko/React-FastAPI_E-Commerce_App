"""
How long notifications are kept, against the real test database: the daily
sweep deletes those past NOTIFICATION_RETENTION_DAYS, and a deleted account's
go at once through the real user-event handler (Redis idempotency included).
Old rows are written with a past date_created; nothing else is faked.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from contracts.events import UserDeletedEvent
from events_consumer.event_handlers import UserEventHandler
from infrastructure.idempotency.idempotency_service import IdempotencyEventService
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.base import Base
from models.notification_models import Notification
from service_layer.notification_retention import NotificationRetention
from settings import get_settings

# The Redis connection is bound to the session loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")

settings = get_settings()
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    await test_database_session_manager.truncate_all_tables(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _notify(db: TestDatabaseSessionManager, user_id: UUID | None, made: datetime) -> UUID:
    async with db.transaction() as session:
        notification = Notification(user_id=user_id, message="Your order shipped.", notification_type="order.shipped",
                                    date_created=made)
        session.add(notification)
        await session.flush()
        return notification.id


async def _remaining(db: TestDatabaseSessionManager, user_id: UUID | None = None) -> int:
    query = select(func.count()).select_from(Notification)
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)
    async with db.transaction() as session:
        return await session.scalar(query)


class TestTheDailySweep:
    async def test_deletes_only_notifications_past_the_retention_period(self, db) -> None:
        days = settings.NOTIFICATION_RETENTION_DAYS
        await _notify(db, uuid4(), NOW - timedelta(days=days + 1))
        await _notify(db, None, NOW - timedelta(days=days + 300))
        kept = await _notify(db, uuid4(), NOW - timedelta(days=days - 1))

        deleted = await NotificationRetention(db, getLogger("test"), retention_days=days).prune(now=NOW)

        assert deleted == 2
        async with db.transaction() as session:
            assert [row.id for row in (await session.execute(select(Notification))).scalars()] == [kept]

    async def test_a_backlog_larger_than_a_batch_is_cleared_in_one_run(self, db) -> None:
        for _ in range(5):
            await _notify(db, uuid4(), NOW - timedelta(days=400))

        retention = NotificationRetention(db, getLogger("test"), retention_days=365, batch_size=2)

        assert await retention.prune(now=NOW) == 5
        assert await _remaining(db) == 0


class TestADeletedAccount:
    @pytest.fixture
    async def handler(self, db) -> AsyncGenerator[UserEventHandler, None]:
        # A prefix of its own, so claims from other runs never collide.
        idempotency = IdempotencyEventService(
            service_prefix=f"notification-test-{uuid4().hex[:8]}",
            logger=getLogger("test"),
            redis_url=settings.NOTIFICATION_SERVICE_REDIS_URL,
        )
        await idempotency.connect()
        try:
            yield UserEventHandler(idempotency, db, getLogger("test"))
        finally:
            await idempotency.close()

    async def test_its_notifications_go_and_no_new_one_is_saved(self, db, handler: UserEventHandler) -> None:
        gone, staying = uuid4(), uuid4()
        for _ in range(3):
            await _notify(db, gone, NOW)
        await _notify(db, staying, NOW)

        await handler.handle(UserDeletedEvent(user_email="gone@example.com", user_id=gone).model_dump(mode="json"))

        assert await _remaining(db, gone) == 0
        assert await _remaining(db) == 1
