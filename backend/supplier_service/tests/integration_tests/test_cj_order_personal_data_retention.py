"""
CJOrderPersonalDataRetention against the real supplier test database. Ended
orders are written with past delivery or update times; nothing is faked.

Rules: 90 days after a CJ order ended (delivered, failed, cancelled or
rejected), the customer's name, street, city, postal code, phone and email
leave its stored request and the attempt's email is cleared, while what was
ordered, how it shipped and what it cost stay; an order still open keeps
everything, however old; an order done once is not done again.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from enums.cj_order_enums import CJOrderAttemptStatus
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.base import Base
from models.cj_order_attempt_models import CJOrderAttempt
from service_layer.cj_order_personal_data_retention import PERSONAL_FIELDS, CJOrderPersonalDataRetention
from settings import get_settings

settings = get_settings()
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
DAYS = settings.CJ_ORDER_PERSONAL_DATA_RETENTION_DAYS

# An order as CJOrderPayloadBuilder sends it.
SENT = {
    "orderNumber": "order-1",
    "shippingCustomerName": "Ann Lee",
    "shippingPhone": "+1 604 555 0101",
    "shippingAddress": "1 Main St",
    "shippingAddress2": "",
    "shippingCity": "Vancouver",
    "shippingProvince": "BC",
    "shippingZip": "V5K 0A1",
    "shippingCountry": "Canada",
    "shippingCountryCode": "CA",
    "email": "ann.lee@example.com",
    "logisticName": "CJPacket Ordinary",
    "fromCountryCode": "CN",
    "products": [{"vid": "vid-1", "quantity": 2}],
}


@pytest.fixture
async def db() -> AsyncGenerator[TestDatabaseSessionManager, None]:
    manager = TestDatabaseSessionManager(database_url=settings.SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test"))
    await manager.recreate_schema(Base.metadata)
    yield manager
    await manager.truncate_all_tables(Base.metadata)
    await manager.close()


async def _order(
    db: TestDatabaseSessionManager, status: CJOrderAttemptStatus, ended_days_ago: float, delivered: bool = False
) -> UUID:
    ended = NOW - timedelta(days=ended_days_ago)
    async with db.transaction() as session:
        attempt = CJOrderAttempt(
            order_id=uuid4(), user_id=uuid4(), user_email="ann.lee@example.com", status=status,
            request_payload=dict(SENT), cj_order_amount_usd=Decimal("12.40"),
            delivered_at=ended if delivered else None,
        )
        session.add(attempt)
        await session.flush()
        order_id = attempt.order_id
    # date_updated is set by the database on every write, so the end of an
    # order that did not deliver is moved into the past directly.
    async with db.transaction() as session:
        await session.execute(
            text("UPDATE cj_order_attempts SET date_updated = :ended WHERE order_id = :order_id"),
            {"ended": ended, "order_id": order_id},
        )
    return order_id


async def _attempt(db: TestDatabaseSessionManager, order_id: UUID) -> CJOrderAttempt:
    async with db.transaction() as session:
        return (await session.execute(select(CJOrderAttempt).where(CJOrderAttempt.order_id == order_id))).scalar_one()


def _retention(db: TestDatabaseSessionManager, **options) -> CJOrderPersonalDataRetention:
    return CJOrderPersonalDataRetention(db, getLogger("test"), retention_days=DAYS, **options)


async def test_an_order_delivered_long_ago_loses_the_customers_details_and_keeps_the_rest(db) -> None:
    order_id = await _order(db, CJOrderAttemptStatus.DELIVERED, DAYS + 1, delivered=True)

    assert await _retention(db).prune(now=NOW) == 1

    attempt = await _attempt(db, order_id)
    assert attempt.request_payload == {key: value for key, value in SENT.items() if key not in PERSONAL_FIELDS}
    assert attempt.request_payload["products"] == SENT["products"]
    assert attempt.request_payload["shippingProvince"] == "BC"
    assert attempt.user_email is None
    assert attempt.personal_data_removed_at == NOW
    assert attempt.cj_order_amount_usd == Decimal("12.40")


@pytest.mark.parametrize(
    "status", [CJOrderAttemptStatus.FAILED, CJOrderAttemptStatus.CANCELLED, CJOrderAttemptStatus.REJECTED]
)
async def test_an_order_that_ended_otherwise_is_measured_from_its_last_change(db, status) -> None:
    old = await _order(db, status, DAYS + 1)
    recent = await _order(db, status, DAYS - 1)

    assert await _retention(db).prune(now=NOW) == 1

    assert (await _attempt(db, old)).user_email is None
    assert (await _attempt(db, recent)).request_payload == SENT


@pytest.mark.parametrize(
    "status",
    [CJOrderAttemptStatus.PAID, CJOrderAttemptStatus.SHIPPED, CJOrderAttemptStatus.RECONCILIATION_REQUIRED],
)
async def test_an_open_order_keeps_everything_however_old(db, status) -> None:
    order_id = await _order(db, status, DAYS + 300)

    assert await _retention(db).prune(now=NOW) == 0

    attempt = await _attempt(db, order_id)
    assert attempt.request_payload == SENT and attempt.user_email == "ann.lee@example.com"


async def test_an_order_done_once_is_not_done_again(db) -> None:
    await _order(db, CJOrderAttemptStatus.DELIVERED, DAYS + 1, delivered=True)
    assert await _retention(db).prune(now=NOW) == 1
    assert await _retention(db).prune(now=NOW + timedelta(days=1)) == 0


async def test_a_backlog_bigger_than_a_batch_goes_in_one_run(db) -> None:
    for _ in range(5):
        await _order(db, CJOrderAttemptStatus.DELIVERED, DAYS + 10, delivered=True)
    assert await _retention(db, batch_size=2).prune(now=NOW) == 5
