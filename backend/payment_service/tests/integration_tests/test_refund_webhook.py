"""
charge.refund.updated against the real payment test database.

The regression these guard: the webhook used to mark the whole payment
refunded on *any* succeeded refund, so after one partial refund the customer
was told the payment was refunded and every later partial refund was refused.
"""

from collections.abc import AsyncGenerator
from logging import getLogger
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from database_layer.payment_repository import PaymentRefundRepository, PaymentRepository
from models.base import Base
from models.outbox_models import OutboxEvent
from models.payment_models import Payment, PaymentRefund
from service_layer.outbox_event_service import OutboxEventService
from service_layer.payment_refund_service import PaymentRefundService, RefundStatus
from service_layer.stripe_refund_webhook_service import StripeRefundWebhookService
from shared.contracts.events import PaymentRefundRequested
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.managers.test_database_session_manager import TestDatabaseSessionManager


pytestmark = pytest.mark.asyncio(loop_scope="session")
AMOUNT = 4_873


class FakeStripe:
    """Creates refunds and remembers what was sent, the way Stripe echoes it back."""

    def __init__(self) -> None:
        self.created: list[tuple[str, int, dict[str, str]]] = []
        self.v1 = SimpleNamespace(refunds=SimpleNamespace(create_async=self._create))

    async def _create(
        self, params: dict[str, str | int | dict[str, str]], options: dict[str, str]
    ) -> SimpleNamespace:
        intent, amount, metadata = params["payment_intent"], params["amount"], params["metadata"]
        assert isinstance(intent, str) and isinstance(amount, int) and isinstance(metadata, dict)
        assert options["idempotency_key"]
        self.created.append((intent, amount, metadata))
        return SimpleNamespace(id=f"re_app_{len(self.created)}")

    def webhook_for(self, index: int) -> dict[str, object]:
        """The charge.refund.updated Stripe sends for the refund created at ``index``."""
        intent, amount, metadata = self.created[index]
        return _refund_event(f"re_app_{index + 1}", intent, amount, metadata)


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _payment(db: TestDatabaseSessionManager) -> Payment:
    payment = Payment(
        order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
        stripe_payment_intent_id=f"pi_{uuid4().hex}", amount=AMOUNT, currency="cad",
        status=PaymentStatus.SUCCEEDED,
    )
    async with db.transaction() as session:
        session.add(payment)
    return payment


def _refund_event(
    refund_id: str, intent: str, amount: int, metadata: dict[str, str] | None = None, status: str = "succeeded"
) -> dict[str, object]:
    """The shape Stripe sends as event.data for charge.refund.updated."""
    return {"object": {
        "id": refund_id, "object": "refund", "amount": amount, "currency": "cad",
        "payment_intent": intent, "status": status, "metadata": metadata or {},
    }}


def _command(order_id: UUID, cents: int) -> PaymentRefundRequested:
    return PaymentRefundRequested(
        order_id=order_id, user_id=uuid4(), user_email="buyer@example.com",
        refund_id=uuid4(), amount_cents=cents, reason="damaged item",
    )


async def _webhook(db: TestDatabaseSessionManager, data: dict[str, object]) -> None:
    async with db.transaction() as session:
        await StripeRefundWebhookService(
            payment_repository=PaymentRepository(session=session),
            refund_repository=PaymentRefundRepository(session=session),
            outbox_event_service=OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)),
            logger=getLogger("test.refund_webhook"),
        ).refund_updated(data)


async def _state(db: TestDatabaseSessionManager, order_id: UUID) -> tuple[Payment, list[PaymentRefund], list[OutboxEvent]]:
    async with db.transaction() as session:
        payment = (await session.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one()
        refunds = (await session.execute(
            select(PaymentRefund).where(PaymentRefund.payment_id == payment.id)
        )).scalars().all()
        events = (await session.execute(select(OutboxEvent).order_by(OutboxEvent.date_created))).scalars().all()
    return payment, list(refunds), list(events)


async def test_our_partial_refunds_webhook_leaves_the_payment_refundable(db) -> None:
    """The live sequence: refund one line, Stripe reports it, refund the shipping."""
    payment = await _payment(db)
    fake = FakeStripe()
    refunds = PaymentRefundService(db, fake, getLogger("t"))

    assert await refunds.refund(_command(payment.order_id, 1_999)) == RefundStatus.SUCCEEDED
    await _webhook(db, fake.webhook_for(0))

    after_webhook, _, events = await _state(db, payment.order_id)
    assert after_webhook.status == PaymentStatus.SUCCEEDED
    assert after_webhook.refunded_cents == 1_999
    assert [e.event_type for e in events] == [PaymentEvents.PAYMENT_REFUNDED]  # only the refund's own

    assert await refunds.refund(_command(payment.order_id, 875)) == RefundStatus.SUCCEEDED
    final, rows, _ = await _state(db, payment.order_id)
    assert final.refunded_cents == 2_874 and final.status == PaymentStatus.SUCCEEDED
    assert sorted(r.status for r in rows) == [RefundStatus.SUCCEEDED, RefundStatus.SUCCEEDED]


async def test_a_dashboard_partial_refund_is_recorded_once_and_announced_as_partial(db) -> None:
    payment = await _payment(db)
    event = _refund_event("re_dashboard_1", payment.stripe_payment_intent_id, 1_000)

    await _webhook(db, event)
    await _webhook(db, event)  # Stripe redelivers

    recorded, rows, events = await _state(db, payment.order_id)
    assert recorded.status == PaymentStatus.SUCCEEDED and recorded.refunded_cents == 1_000
    assert [(r.stripe_refund_id, r.amount_cents, r.status) for r in rows] == [
        ("re_dashboard_1", 1_000, RefundStatus.SUCCEEDED)
    ]
    assert len(events) == 1
    payload = events[0].payload
    assert payload["refund_id"] == str(rows[0].id) and payload["refunded_amount_cents"] == 1_000


async def test_a_dashboard_refund_of_the_rest_marks_the_payment_refunded(db) -> None:
    payment = await _payment(db)
    await PaymentRefundService(db, FakeStripe(), getLogger("t")).refund(_command(payment.order_id, 1_999))

    await _webhook(db, _refund_event("re_dashboard_2", payment.stripe_payment_intent_id, AMOUNT - 1_999))

    recorded, _, events = await _state(db, payment.order_id)
    assert recorded.status == PaymentStatus.REFUNDED and recorded.refundable_cents == 0
    assert events[-1].payload["refund_id"] is None  # a whole-payment refund


async def test_a_refund_that_did_not_succeed_or_is_unknown_changes_nothing(db) -> None:
    payment = await _payment(db)

    await _webhook(db, _refund_event("re_pending", payment.stripe_payment_intent_id, 500, status="pending"))
    await _webhook(db, _refund_event("re_elsewhere", "pi_not_ours", 500))  # not raised: Stripe would retry for days

    recorded, rows, events = await _state(db, payment.order_id)
    assert recorded.refunded_cents == 0 and rows == [] and events == []
