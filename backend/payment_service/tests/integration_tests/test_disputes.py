"""Stripe chargebacks recorded against the real payment test database."""

from collections.abc import AsyncGenerator
from logging import getLogger
from uuid import uuid4

import pytest
from sqlalchemy import select

from database_layer.payment_repository import PaymentDisputeRepository, PaymentRepository
from models.base import Base
from models.outbox_models import OutboxEvent
from models.payment_models import Payment, PaymentDispute
from service_layer.outbox_event_service import OutboxEventService
from service_layer.payment_dispute_service import PaymentDisputeService
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.managers.test_database_session_manager import TestDatabaseSessionManager


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _payment(db: TestDatabaseSessionManager) -> str:
    intent = f"pi_{uuid4().hex}"
    async with db.transaction() as session:
        session.add(Payment(
            order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
            stripe_payment_intent_id=intent, amount=7_322, currency="cad", status=PaymentStatus.SUCCEEDED,
        ))
    return intent


def _dispute(intent: str, status: str, dispute_id: str = "dp_test_1") -> dict:
    """The shape Stripe sends as event.data for charge.dispute.*."""
    return {"object": {
        "id": dispute_id, "object": "dispute", "amount": 7_322, "currency": "cad",
        "reason": "fraudulent", "status": status, "payment_intent": intent, "charge": "ch_test",
        "evidence_details": {"due_by": 1_790_000_000},
    }}


async def _handle(db: TestDatabaseSessionManager, action: str, data: dict) -> None:
    async with db.transaction() as session:
        service = PaymentDisputeService(
            payment_repository=PaymentRepository(session=session),
            dispute_repository=PaymentDisputeRepository(session=session),
            outbox_event_service=OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)),
            logger=getLogger("test.disputes"),
        )
        await getattr(service, action)(data)


async def _state(db: TestDatabaseSessionManager) -> tuple[list[PaymentDispute], list[str]]:
    async with db.transaction() as session:
        disputes = (await session.execute(select(PaymentDispute))).scalars().all()
        events = (await session.execute(select(OutboxEvent.event_type))).scalars().all()
    return list(disputes), list(events)


async def test_an_opened_dispute_is_recorded_and_announced(db) -> None:
    intent = await _payment(db)
    await _handle(db, "opened", _dispute(intent, "needs_response"))

    disputes, events = await _state(db)
    assert len(disputes) == 1 and disputes[0].status == "needs_response"
    assert disputes[0].evidence_due_by is not None and disputes[0].payment_id is not None
    assert events == [PaymentEvents.PAYMENT_DISPUTE_OPENED]


async def test_a_repeated_webhook_changes_nothing(db) -> None:
    intent = await _payment(db)
    await _handle(db, "opened", _dispute(intent, "needs_response"))
    await _handle(db, "opened", _dispute(intent, "needs_response"))

    disputes, events = await _state(db)
    assert len(disputes) == 1 and events == [PaymentEvents.PAYMENT_DISPUTE_OPENED]


async def test_closing_updates_the_row_and_announces_the_outcome(db) -> None:
    intent = await _payment(db)
    await _handle(db, "opened", _dispute(intent, "needs_response"))
    await _handle(db, "updated", _dispute(intent, "under_review"))
    await _handle(db, "closed", _dispute(intent, "lost"))

    disputes, events = await _state(db)
    assert disputes[0].status == "lost"
    assert events == [PaymentEvents.PAYMENT_DISPUTE_OPENED, PaymentEvents.PAYMENT_DISPUTE_CLOSED]


async def test_a_dispute_on_an_unknown_charge_is_still_recorded(db) -> None:
    await _handle(db, "opened", _dispute("pi_not_ours", "needs_response", "dp_unknown"))
    disputes, events = await _state(db)
    assert len(disputes) == 1 and disputes[0].payment_id is None
    assert events == []  # no order to flag
