"""
How long product-service keeps what customers made, against the real product
test database, the real private test bucket and Redis (the event's claim).
Old designs and refusals are rows written with a past date_created; nothing
else is faked.

Rules: a design no order holds is deleted (object and row) once older than
GENERATED_DESIGN_RETENTION_DAYS; a design an order holds stays however old,
and one whose only hold was released (a cancelled order) does not; a deleted
account's unordered designs go at once, whatever their age, and its id leaves
the refusal records, which stay; refusals go after DESIGN_REFUSAL_RETENTION_DAYS.
"""

import hashlib
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from contracts.events import UserDeletedEvent
from event_consumer.account_deletion_consumer import AccountDeletionConsumer
from infrastructure.idempotency.idempotency_service import IdempotencyEventService
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.base import Base
from models.design_moderation_refusal_models import DesignModerationRefusal
from models.generated_design_models import GeneratedDesign
from models.retained_artwork_models import RetainedArtwork
from resources import create_deleted_account_cleanup, create_design_refusal_retention, create_design_retention
from service_layer.design_moderation import ModerationCategory, ModerationStage
from service_layer.design_refusal_log import DatabaseDesignRefusalLog
from settings import get_settings
from storage.object_storage_provider import ObjectStorageProvider
from storage.object_store import ObjectStore, ObjectWrite
from tests.design_moderation_fakes import refused

# The Redis connection is bound to the session loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")

settings = get_settings()
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
DESIGN_DAYS = settings.GENERATED_DESIGN_RETENTION_DAYS
REFUSAL_DAYS = settings.DESIGN_REFUSAL_RETENTION_DAYS


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.truncate_all_tables(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


@pytest.fixture
def store() -> ObjectStore:
    assert settings.AWS_S3_PRIVATE_BUCKET and settings.AWS_S3_PRIVATE_BUCKET.endswith("-test")
    return ObjectStorageProvider(settings).private()


async def _design(
    db: TestDatabaseSessionManager, store: ObjectStore, user_id: UUID | None, days_old: float
) -> str:
    """A stored design (object in the bucket, row in generated_designs) made that many days ago."""
    key = f"generated-designs/2026/07/{uuid4().hex}.png"
    await store.put(ObjectWrite(key=key, body=PNG, content_type="image/png", cache_control="private, max-age=60",
                                sha256=hashlib.sha256(PNG).hexdigest()))
    async with db.transaction() as session:
        session.add(GeneratedDesign(key=key, user_id=user_id, date_created=NOW - timedelta(days=days_old)))
    return key


async def _hold(db: TestDatabaseSessionManager, key: str, released: bool = False) -> None:
    async with db.transaction() as session:
        session.add(RetainedArtwork(artwork_key=key, order_id=uuid4(),
                                    released_at=NOW if released else None,
                                    release_reason="order cancelled" if released else None))


async def _rows(db: TestDatabaseSessionManager) -> set[str]:
    async with db.transaction() as session:
        return set((await session.execute(select(GeneratedDesign.key))).scalars())


async def _kept(store: ObjectStore, *keys: str) -> list[bool]:
    return [await store.exists(key) for key in keys]


class TestUnorderedDesigns:
    async def test_go_once_past_the_retention_period_object_and_row(self, db, store) -> None:
        old = await _design(db, store, uuid4(), DESIGN_DAYS + 1)
        young = await _design(db, store, uuid4(), DESIGN_DAYS - 1)

        assert await create_design_retention(db).prune(now=NOW) == 1

        assert await _kept(store, old, young) == [False, True]
        assert await _rows(db) == {young}

    async def test_a_design_an_order_holds_stays_however_old(self, db, store) -> None:
        ordered = await _design(db, store, uuid4(), DESIGN_DAYS + 400)
        await _hold(db, ordered)

        assert await create_design_retention(db).prune(now=NOW) == 0

        assert await _kept(store, ordered) == [True]
        assert await _rows(db) == {ordered}

    async def test_a_design_whose_order_was_cancelled_is_unordered_again(self, db, store) -> None:
        cancelled = await _design(db, store, uuid4(), DESIGN_DAYS + 1)
        await _hold(db, cancelled, released=True)

        assert await create_design_retention(db).prune(now=NOW) == 1
        assert await _kept(store, cancelled) == [False]

    async def test_a_backlog_bigger_than_a_batch_goes_in_one_run(self, db, store) -> None:
        keys = [await _design(db, store, uuid4(), DESIGN_DAYS + 5) for _ in range(5)]
        retention = create_design_retention(db)
        retention._batch_size = 2

        assert await retention.prune(now=NOW) == 5
        assert await _kept(store, *keys) == [False] * 5


class TestRefusalRecords:
    async def test_go_once_past_the_retention_period(self, db) -> None:
        log = DatabaseDesignRefusalLog(db)
        await log.record(uuid4(), "old request", "Neon", refused(ModerationStage.PROMPT))
        await log.record(uuid4(), "recent request", "Neon", refused(ModerationStage.IMAGE))
        async with db.transaction() as session:
            old = (await session.execute(
                select(DesignModerationRefusal).where(DesignModerationRefusal.prompt == "old request")
            )).scalar_one()
            old.date_created = NOW - timedelta(days=REFUSAL_DAYS + 1)

        assert await create_design_refusal_retention(db).prune(now=NOW) == 1

        async with db.transaction() as session:
            prompts = list((await session.execute(select(DesignModerationRefusal.prompt))).scalars())
        assert prompts == ["recent request"]


class TestADeletedAccount:
    @pytest.fixture
    async def consumer(self, db) -> AsyncGenerator[AccountDeletionConsumer, None]:
        # A prefix of its own, so claims from other runs never collide.
        idempotency = IdempotencyEventService(
            service_prefix=f"product-test-{uuid4().hex[:8]}",
            logger=getLogger("test"),
            redis_url=settings.PRODUCT_SERVICE_REDIS_URL,
        )
        await idempotency.connect()
        try:
            yield AccountDeletionConsumer(create_deleted_account_cleanup(db), idempotency, getLogger("test"))
        finally:
            await idempotency.close()

    @staticmethod
    def _deleted(user_id: UUID) -> dict:
        return UserDeletedEvent(user_email="gone@example.com", user_id=user_id).model_dump(mode="json")

    async def test_its_unordered_designs_go_at_once_and_ordered_and_others_stay(self, db, store, consumer) -> None:
        gone, staying = uuid4(), uuid4()
        fresh = await _design(db, store, gone, days_old=1)
        ordered = await _design(db, store, gone, days_old=1)
        await _hold(db, ordered)
        someone_elses = await _design(db, store, staying, days_old=1)

        await consumer.handle_user_event(self._deleted(gone))

        assert await _kept(store, fresh, ordered, someone_elses) == [False, True, True]
        assert await _rows(db) == {ordered, someone_elses}

    async def test_its_refusals_stay_without_its_id(self, db, consumer) -> None:
        gone, staying = uuid4(), uuid4()
        log = DatabaseDesignRefusalLog(db)
        await log.record(gone, "Mickey Mouse surfing", "Cartoon",
                         refused(ModerationStage.PROMPT, ModerationCategory.CHARACTER))
        await log.record(staying, "A swoosh", "Minimal", refused(ModerationStage.PROMPT))

        await consumer.handle_user_event(self._deleted(gone))

        async with db.transaction() as session:
            rows = {row.prompt: row.user_id for row in (await session.execute(select(DesignModerationRefusal))).scalars()}
        assert rows == {"Mickey Mouse surfing": None, "A swoosh": staying}

    async def test_a_redelivered_event_changes_nothing(self, db, store, consumer) -> None:
        gone = uuid4()
        message = self._deleted(gone)
        await consumer.handle_user_event(message)
        # A design recorded after the first delivery is not touched by a stale one.
        later = await _design(db, store, gone, days_old=0)
        await consumer.handle_user_event(message)
        assert await _kept(store, later) == [True]
