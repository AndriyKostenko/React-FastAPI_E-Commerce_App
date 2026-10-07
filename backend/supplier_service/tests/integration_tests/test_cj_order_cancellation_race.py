"""
order.confirmed and order.cancelled for the same order, against real Postgres.

The two events arrive on separate queues. After a backlog (found live when
supplier-service restarted) the cancellation was handled first, found no CJ
attempt, left nothing behind, and the confirmation then submitted a CJ order
for an order whose card hold was already voided. Row locks and the
``cancelled_at`` stamp are what stop that, so they run on a real database;
only CJ, the payload builder and the FX rate are faked.
"""

from collections.abc import AsyncGenerator
from decimal import Decimal
from logging import Logger, getLogger
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from enums.cj_order_enums import CJOrderAttemptStatus
from event_consumer.supplier_event_consumer import SupplierEventConsumer
from models.base import Base
from models.cj_order_attempt_models import CJOrderAttempt
from models.outbox_models import OutboxEvent
from service_layer.cj_api_client import (
    CJDropshippingNetworkError,
    CJDropshippingNotFoundError,
    CJDropshippingUnavailableError,
)
from shared.enums.event_enums import OrderEvents
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.settings import Settings, get_settings
from shared.utils.supplier_pricing import SupplierRetailPricing


pytestmark = pytest.mark.asyncio(loop_scope="session")
CJ_ORDER = "CJ-SANDBOX-1"


class InMemoryIdempotency:
    """The Redis-backed claim store, kept in a dict: claims are not under test."""

    def __init__(self) -> None:
        self.claimed: set[str] = set()

    async def try_claim_event(self, event_id: str, event_type: str) -> bool:
        if str(event_id) in self.claimed:
            return False
        self.claimed.add(str(event_id))
        return True

    async def mark_event_as_processed(self, event_id: str, event_type: str, order_id: UUID | None = None, result: str = "") -> None:
        return None

    async def release_claim(self, event_id: str, event_type: str) -> None:
        self.claimed.discard(str(event_id))


class FakeCJ:
    """CJ's order endpoints; each one can be scripted per test."""

    def __init__(self) -> None:
        self.create_order_v2 = AsyncMock(
            return_value={"result": True, "code": 200, "data": {"orderId": CJ_ORDER}}
        )
        self.get_order_detail = AsyncMock(side_effect=CJDropshippingNotFoundError("order not found"))
        self.delete_order = AsyncMock(return_value={"result": True, "code": 200})


@pytest.fixture
async def db() -> AsyncGenerator[TestDatabaseSessionManager, None]:
    manager = TestDatabaseSessionManager(
        database_url=get_settings().SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test")
    )
    await manager.init_db(Base.metadata)
    yield manager
    await manager.truncate_all_tables(Base.metadata)
    await manager.close()


@pytest.fixture(autouse=True)
def fixed_fx_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    async def live(cls: type[SupplierRetailPricing], settings: Settings, logger: Logger) -> SupplierRetailPricing:
        return cls.from_settings(settings, Decimal("1.37"))

    monkeypatch.setattr(SupplierRetailPricing, "live", classmethod(live))


def _consumer(db: TestDatabaseSessionManager, cj: FakeCJ) -> SupplierEventConsumer:
    consumer = SupplierEventConsumer(
        logger=getLogger("test.cancellation_race"),
        settings=get_settings(),
        database=db,
        idempotency_service=InMemoryIdempotency(),
        cj_api_client=cj,
        product_service_client=SimpleNamespace(),
        publisher=SimpleNamespace(),
    )
    # Address validation, CJ id mapping and the stock check have their own tests.
    consumer._build_cj_order_payload = AsyncMock(return_value={"orderNumber": "local", "isSandbox": 1})
    consumer.payment_service.advance = AsyncMock(return_value=CJOrderAttemptStatus.PAID)
    return consumer


def _messages(order_id: UUID) -> tuple[dict[str, object], dict[str, object]]:
    user = {"order_id": str(order_id), "user_id": str(uuid4()), "user_email": "buyer@example.com"}
    confirmed = {
        **user, "event_id": str(uuid4()), "service": "order-service", "event_type": OrderEvents.ORDER_CONFIRMED,
        "items": [{"product_id": str(uuid4()), "variant_id": str(uuid4()), "quantity": 1,
                   "price": 19.99, "fulfillment_type": "cj"}],
        "address": {"street": "123 Queen St W", "city": "Toronto", "province": "ON",
                    "postal_code": "M5H 2M9", "country": "Canada", "country_code": "CA",
                    "name": "Buyer", "phone": "4165550123"},
        "shipping_cost_usd": 4.5, "shipping_logistic_name": "CJPacket Ordinary",
    }
    cancelled = {**user, "event_id": str(uuid4()), "service": "order-service",
                 "event_type": OrderEvents.ORDER_CANCELLED, "reason": "Customer changed their mind"}
    return confirmed, cancelled


async def _state(db: TestDatabaseSessionManager, order_id: UUID) -> tuple[CJOrderAttempt, list[str]]:
    async with db.transaction() as session:
        attempt = (await session.execute(
            select(CJOrderAttempt).where(CJOrderAttempt.order_id == order_id)
        )).scalar_one()
        events = (await session.execute(select(OutboxEvent.event_type))).scalars().all()
    return attempt, list(events)


async def test_a_cancellation_handled_first_stops_the_cj_order(db) -> None:
    order_id, cj = uuid4(), FakeCJ()
    confirmed, cancelled = _messages(order_id)
    consumer = _consumer(db, cj)

    await consumer.handle_order_cancelled(cancelled)
    await consumer.handle_order_confirmed(confirmed)

    attempt, events = await _state(db, order_id)
    assert attempt.status == CJOrderAttemptStatus.CANCELLED and attempt.cancelled_at is not None
    cj.create_order_v2.assert_not_awaited()
    consumer.payment_service.advance.assert_not_awaited()
    assert OrderEvents.CJ_ORDER_CREATED not in events


async def test_a_cancellation_while_the_order_is_prepared_stops_the_post(db) -> None:
    """Found live: the cancel lands after the attempt was first read, before the POST."""
    order_id, cj = uuid4(), FakeCJ()
    confirmed, cancelled = _messages(order_id)
    consumer = _consumer(db, cj)

    async def build_while_cancelled(event: object) -> dict[str, object]:
        await consumer.handle_order_cancelled(cancelled)
        return {"orderNumber": "local", "isSandbox": 1}

    consumer._build_cj_order_payload = AsyncMock(side_effect=build_while_cancelled)
    await consumer.handle_order_confirmed(confirmed)

    attempt, events = await _state(db, order_id)
    assert attempt.status == CJOrderAttemptStatus.CANCELLED
    cj.create_order_v2.assert_not_awaited()
    consumer.payment_service.advance.assert_not_awaited()
    assert OrderEvents.CJ_ORDER_CREATED not in events


async def test_a_cancellation_during_the_cj_post_withdraws_the_new_order(db) -> None:
    order_id, cj = uuid4(), FakeCJ()
    confirmed, cancelled = _messages(order_id)
    consumer = _consumer(db, cj)

    async def create_while_cancelled(payload: dict[str, object]) -> dict[str, object]:
        # The cancellation is handled while CJ is still answering the POST.
        await consumer.handle_order_cancelled(cancelled)
        return {"result": True, "code": 200, "data": {"orderId": CJ_ORDER}}

    cj.create_order_v2.side_effect = create_while_cancelled
    await consumer.handle_order_confirmed(confirmed)

    attempt, events = await _state(db, order_id)
    cj.delete_order.assert_awaited_once_with(CJ_ORDER)
    assert attempt.status == CJOrderAttemptStatus.CANCELLED and attempt.cj_order_number == CJ_ORDER
    consumer.payment_service.advance.assert_not_awaited()
    assert OrderEvents.CJ_ORDER_CREATED not in events


async def test_an_interrupted_withdrawal_is_finished_and_never_paid(db) -> None:
    order_id, cj = uuid4(), FakeCJ()
    confirmed, cancelled = _messages(order_id)
    consumer = _consumer(db, cj)
    real_advance = SupplierEventConsumer(
        logger=getLogger("t"), settings=get_settings(), database=db,
        idempotency_service=InMemoryIdempotency(), cj_api_client=cj,
        product_service_client=SimpleNamespace(), publisher=SimpleNamespace(),
    ).payment_service.advance

    async def create_while_cancelled(payload: dict[str, object]) -> dict[str, object]:
        await consumer.handle_order_cancelled(cancelled)
        return {"result": True, "code": 200, "data": {"orderId": CJ_ORDER}}

    cj.create_order_v2.side_effect = create_while_cancelled
    cj.delete_order.side_effect = CJDropshippingNetworkError("connection reset")
    with pytest.raises(CJDropshippingNetworkError):
        await consumer.handle_order_confirmed(confirmed)

    # The payment retry task finds a created CJ order: it must not pay it.
    assert await real_advance(order_id) == CJOrderAttemptStatus.CREATED

    cj.delete_order.side_effect = None
    await consumer.handle_order_confirmed(confirmed)  # the message is redelivered

    attempt, events = await _state(db, order_id)
    assert attempt.status == CJOrderAttemptStatus.CANCELLED
    assert cj.delete_order.await_count == 2
    assert OrderEvents.CJ_ORDER_CREATED not in events


async def test_a_post_cj_never_received_is_submitted_again(db) -> None:
    order_id, cj = uuid4(), FakeCJ()
    confirmed, _ = _messages(order_id)
    consumer = _consumer(db, cj)
    cj.create_order_v2.side_effect = [
        CJDropshippingUnavailableError("CJ API returned 429: QPS limit is 1 time/1second"),
        {"result": True, "code": 200, "data": {"orderId": CJ_ORDER}},
    ]

    with pytest.raises(CJDropshippingUnavailableError):
        await consumer.handle_order_confirmed(confirmed)
    first, _ = await _state(db, order_id)
    assert first.status == CJOrderAttemptStatus.CREATING

    await consumer.handle_order_confirmed(confirmed)  # the retry queue redelivers it

    attempt, events = await _state(db, order_id)
    assert attempt.status == CJOrderAttemptStatus.CREATED and attempt.cj_order_number == CJ_ORDER
    assert cj.create_order_v2.await_count == 2
    assert events == [OrderEvents.CJ_ORDER_CREATED]
    consumer.payment_service.advance.assert_awaited_once_with(order_id)
