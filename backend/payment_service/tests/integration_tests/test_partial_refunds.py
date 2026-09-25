"""
Partial refunds against the real payment test database. Locking, reservations
and idempotency are database behaviour, so only Stripe is replaced — by a
recording fake that can also fail the way Stripe does.
"""

import asyncio
from collections.abc import AsyncGenerator
from logging import getLogger
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import stripe
from sqlalchemy import select

from models.base import Base
from models.outbox_models import OutboxEvent
from models.payment_models import Payment, PaymentRefund
from service_layer.payment_refund_service import PaymentRefundService, RefundStatus
from shared.contracts.events import PaymentRefundRequested
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.managers.test_database_session_manager import TestDatabaseSessionManager


pytestmark = pytest.mark.asyncio(loop_scope="session")
AMOUNT = 10_000  # $100.00


class FakeStripe:
    """Records refunds; can be told to fail the next call."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str]] = []
        self.fail_with: Exception | None = None
        self.v1 = SimpleNamespace(refunds=SimpleNamespace(create_async=self._create))

    async def _create(self, params: dict[str, object], options: dict[str, str]) -> SimpleNamespace:
        if self.fail_with is not None:
            error, self.fail_with = self.fail_with, None
            raise error
        self.calls.append((params, options["idempotency_key"]))
        return SimpleNamespace(id=f"re_{len(self.calls)}")


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _payment(db: TestDatabaseSessionManager, status: PaymentStatus) -> UUID:
    order_id = uuid4()
    async with db.transaction() as session:
        session.add(Payment(
            order_id=order_id, user_id=uuid4(), user_email="buyer@example.com",
            stripe_payment_intent_id=f"pi_{uuid4().hex}", amount=AMOUNT, currency="cad", status=status,
        ))
    return order_id


def _command(order_id: UUID, cents: int, refund_id: UUID | None = None) -> PaymentRefundRequested:
    return PaymentRefundRequested(
        order_id=order_id, user_id=uuid4(), user_email="buyer@example.com",
        refund_id=refund_id or uuid4(), amount_cents=cents, reason="damaged item",
    )


async def _state(db: TestDatabaseSessionManager, order_id: UUID) -> tuple[Payment, list[str]]:
    async with db.transaction() as session:
        payment = (await session.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one()
        events = (await session.execute(select(OutboxEvent.event_type))).scalars().all()
    return payment, list(events)


async def test_a_captured_payment_is_partly_refunded(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    fake = FakeStripe()
    command = _command(order_id, 2_500)

    assert await PaymentRefundService(db, fake, getLogger("t")).refund(command) == RefundStatus.SUCCEEDED

    payment, events = await _state(db, order_id)
    assert payment.refunded_cents == 2_500 and payment.status == PaymentStatus.SUCCEEDED
    assert fake.calls == [({"payment_intent": payment.stripe_payment_intent_id, "amount": 2_500},
                           f"payment_refund:partial:{command.refund_id}")]
    assert events == [PaymentEvents.PAYMENT_REFUNDED]


async def test_more_than_is_left_is_refused_and_nothing_moves(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    fake = FakeStripe()
    await PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 8_000))

    status = await PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 3_000))

    payment, events = await _state(db, order_id)
    assert status == RefundStatus.FAILED
    assert payment.refunded_cents == 8_000 and len(fake.calls) == 1
    assert events[-1] == PaymentEvents.PAYMENT_REFUND_FAILED


async def test_a_redelivered_command_refunds_once(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    fake = FakeStripe()
    command = _command(order_id, 1_000)
    service = PaymentRefundService(db, fake, getLogger("t"))

    await service.refund(command)
    await service.refund(command)

    payment, _ = await _state(db, order_id)
    assert len(fake.calls) == 1 and payment.refunded_cents == 1_000


async def test_before_capture_the_card_is_charged_less(db) -> None:
    order_id = await _payment(db, PaymentStatus.AUTHORIZED)
    fake = FakeStripe()

    status = await PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 3_000))

    payment, events = await _state(db, order_id)
    assert status == RefundStatus.REDUCED_CAPTURE
    assert payment.capture_reduction_cents == 3_000 and payment.refunded_cents == 0
    assert fake.calls == []  # nothing was charged, so nothing is refunded
    assert events == [PaymentEvents.PAYMENT_REFUNDED]


async def test_a_reduction_that_would_void_the_hold_is_refused(db) -> None:
    order_id = await _payment(db, PaymentStatus.AUTHORIZED)
    status = await PaymentRefundService(db, FakeStripe(), getLogger("t")).refund(_command(order_id, AMOUNT))
    payment, _ = await _state(db, order_id)
    assert status == RefundStatus.FAILED and payment.capture_reduction_cents == 0


async def test_a_definitive_stripe_refusal_releases_the_reservation(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    fake = FakeStripe()
    fake.fail_with = stripe.InvalidRequestError("charge already refunded", param="amount")

    status = await PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 1_000))

    payment, events = await _state(db, order_id)
    assert status == RefundStatus.FAILED and payment.refunded_cents == 0
    assert events == [PaymentEvents.PAYMENT_REFUND_FAILED]


async def test_an_uncertain_stripe_error_is_retried_with_the_same_key(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    fake = FakeStripe()
    fake.fail_with = stripe.APIConnectionError("connection reset")
    command = _command(order_id, 1_500)
    service = PaymentRefundService(db, fake, getLogger("t"))

    with pytest.raises(stripe.APIConnectionError):
        await service.refund(command)  # the command will be redelivered
    async with db.transaction() as session:
        pending = await session.get(PaymentRefund, command.refund_id)
    assert pending is not None and pending.status == RefundStatus.PENDING

    assert await service.refund(command) == RefundStatus.SUCCEEDED
    payment, _ = await _state(db, order_id)
    assert payment.refunded_cents == 1_500  # reserved once, not twice
    assert [key for _, key in fake.calls] == [f"payment_refund:partial:{command.refund_id}"]


async def test_concurrent_refunds_cannot_overdraw(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    fake = FakeStripe()

    results = await asyncio.gather(
        PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 6_000)),
        PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 6_000)),
    )

    payment, _ = await _state(db, order_id)
    assert sorted(results) == sorted([RefundStatus.SUCCEEDED, RefundStatus.FAILED])
    assert payment.refunded_cents == 6_000 and len(fake.calls) == 1


async def test_refunding_everything_in_parts_marks_the_payment_refunded(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED)
    service = PaymentRefundService(db, FakeStripe(), getLogger("t"))
    await service.refund(_command(order_id, 4_000))
    await service.refund(_command(order_id, 6_000))
    payment, _ = await _state(db, order_id)
    assert payment.status == PaymentStatus.REFUNDED and payment.refunded_cents == AMOUNT
