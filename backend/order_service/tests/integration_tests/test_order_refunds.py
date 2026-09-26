"""
Partial refunds through the admin API, against the real order test database.
The confirmed order comes from the production-queue fixture: a real custom
order confirmed through the payment path, with one job on the queue.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from database_layer.order_refund_repository import OrderRefundRepository
from events_consumer.order_event_consumer import OrderEventConsumer
from database_layer.order_repository import OrderRepository
from database_layer.order_saga_repository import OrderSagaRepository
from exceptions.order_exceptions import InvalidOrderRefundError
from models.order_models import Order
from models.outbox_models import OutboxEvent
from schemas.order_refund_schemas import RefundLineRequest, RefundRequest
from service_layer.order_refund_service import OrderRefundService, RefundState
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import PaymentDisputeEvent
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import PaymentCommands, PaymentEvents
from shared.enums.status_enums import OrderStatus
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.testing.signing_keys import ANONYMOUS
from tests.conftest import SIGNING_KEYS
from tests.constants import TEST_API
from tests.integration_tests.test_production_routes import PRODUCTION_API, queued_job  # noqa: F401 (fixture)


def _refunds_url(order_id: str) -> str:
    return f"{TEST_API}/admin/orders/{order_id}/refunds"


async def _line(db: TestDatabaseSessionManager, order_id: str) -> tuple[str, int, Decimal]:
    async with db.transaction() as session:
        order = await OrderRepository(session).get_with_fulfillment(UUID(order_id))
        item = order.items[0]
        return str(item.id), item.quantity, Decimal(item.price)


async def _refund_commands(db: TestDatabaseSessionManager) -> list[dict]:
    async with db.transaction() as session:
        rows = (await session.execute(
            select(OutboxEvent.payload).where(OutboxEvent.event_type == PaymentCommands.REFUND_REQUESTED)
        )).scalars().all()
    return list(rows)


async def test_an_admin_refunds_one_line(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _, price = await _line(test_database_session_manager, order_id)

    response = await integration_client.post(
        _refunds_url(order_id), json={"lines": [{"order_item_id": item_id, "quantity": 1}], "reason": "print faded"}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(body["amount"]) == price and body["status"] == RefundState.REQUESTED
    commands = await _refund_commands(test_database_session_manager)
    assert len(commands) == 1
    assert commands[0]["amount_cents"] == int(price * 100)
    assert commands[0]["refund_id"] == body["id"]


async def test_more_than_was_bought_is_refused(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, quantity, _ = await _line(test_database_session_manager, order_id)

    response = await integration_client.post(
        _refunds_url(order_id), json={"lines": [{"order_item_id": item_id, "quantity": quantity + 1}], "reason": "x" * 5}
    )

    assert response.status_code == 422
    assert await _refund_commands(test_database_session_manager) == []


async def test_shipping_is_refunded_at_most_once(integration_client: AsyncClient, queued_job: dict) -> None:  # noqa: F811
    url = _refunds_url(queued_job["order"]["id"])
    first = await integration_client.post(url, json={"include_shipping": True, "reason": "late delivery"})
    second = await integration_client.post(url, json={"include_shipping": True, "reason": "late delivery"})
    # A zero-shipping order refuses the first as "nothing to refund"; either way
    # the second can never succeed.
    assert first.status_code in (201, 422)
    assert second.status_code == 422


async def test_a_pending_order_cannot_be_partly_refunded(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    async with test_database_session_manager.transaction() as session:
        (await session.get(Order, UUID(order_id))).status = OrderStatus.PENDING
    item_id, _, _ = await _line(test_database_session_manager, order_id)

    response = await integration_client.post(
        _refunds_url(order_id), json={"lines": [{"order_item_id": item_id, "quantity": 1}], "reason": "no charge yet"}
    )
    assert response.status_code == 409


@pytest.mark.parametrize(("caller", "status"), [(ANONYMOUS, 401), (SIGNING_KEYS.caller_auth(user_id=uuid4()), 403)])
async def test_only_admins_refund(
    integration_client: AsyncClient, queued_job: dict, caller, status: int  # noqa: F811
) -> None:
    response = await integration_client.post(
        _refunds_url(queued_job["order"]["id"]), json={"include_shipping": True, "reason": "please"}, auth=caller
    )
    assert response.status_code == status


def _service(session) -> OrderRefundService:
    return OrderRefundService(
        order_repository=OrderRepository(session=session),
        saga_repository=OrderSagaRepository(session),
        refund_repository=OrderRefundRepository(session),
        outbox_event_service=OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)),
    )


async def test_a_failed_refund_frees_the_line_again(
    queued_job: dict, test_database_session_manager: TestDatabaseSessionManager  # noqa: F811
) -> None:
    order_id = UUID(queued_job["order"]["id"])
    item_id, quantity, _ = await _line(test_database_session_manager, str(order_id))
    whole_line = RefundRequest(lines=[RefundLineRequest(order_item_id=UUID(item_id), quantity=quantity)], reason="broken")

    async with test_database_session_manager.transaction() as session:
        refund = await _service(session).request(order_id, whole_line, requested_by=None)
    async with test_database_session_manager.transaction() as session:
        await _service(session).record_result(refund.id, succeeded=False, failure_reason="card closed")

    async with test_database_session_manager.transaction() as session:
        again = await _service(session).request(order_id, whole_line, requested_by=None)
    assert again.status == RefundState.REQUESTED


async def test_two_concurrent_refunds_of_the_same_line_cannot_both_pass(
    queued_job: dict, test_database_session_manager: TestDatabaseSessionManager  # noqa: F811
) -> None:
    order_id = UUID(queued_job["order"]["id"])
    item_id, quantity, _ = await _line(test_database_session_manager, str(order_id))
    whole_line = RefundRequest(lines=[RefundLineRequest(order_item_id=UUID(item_id), quantity=quantity)], reason="dup")

    async def attempt() -> str:
        try:
            async with test_database_session_manager.transaction() as session:
                await _service(session).request(order_id, whole_line, requested_by=None)
                await asyncio.sleep(0.2)  # hold the saga lock so the two really overlap
            return "created"
        except InvalidOrderRefundError:
            return "refused"

    assert sorted(await asyncio.gather(attempt(), attempt())) == ["created", "refused"]


async def test_cancelling_an_unprinted_job_refunds_its_line(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    job_id = queued_job["job"]["id"]

    response = await integration_client.post(f"{PRODUCTION_API}/{job_id}/cancel", json={"reason": "blank out of stock"})

    assert response.status_code == 200, response.text
    refunds = (await integration_client.get(_refunds_url(queued_job["order"]["id"]))).json()
    assert len(refunds) == 1 and refunds[0]["requested_by"] is None
    assert "before printing" in refunds[0]["reason"]


async def test_a_job_cancelled_after_printing_is_left_to_a_human(
    integration_client: AsyncClient, queued_job: dict  # noqa: F811
) -> None:
    job_id = queued_job["job"]["id"]
    assert (await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})).status_code == 200
    assert (await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})).status_code == 200

    cancelled = await integration_client.post(f"{PRODUCTION_API}/{job_id}/cancel", json={"reason": "misprint"})

    assert cancelled.status_code == 200
    assert cancelled.json()["reconciliation_required"] is True
    assert (await integration_client.get(_refunds_url(queued_job["order"]["id"]))).json() == []


async def test_a_dispute_flags_the_order_then_records_the_outcome(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    idempotency = MagicMock(
        try_claim_event=AsyncMock(return_value=True), mark_event_as_processed=AsyncMock(), release_claim=AsyncMock()
    )
    consumer = OrderEventConsumer(
        logger=MagicMock(), database=test_database_session_manager,
        idempotency_service=idempotency, event_publisher=MagicMock(),
    )
    order = queued_job["order"]

    def event(event_type: str, status: str) -> dict:
        return PaymentDisputeEvent(
            event_type=event_type, order_id=order["id"], user_id=order["user_id"], user_email=order["user_email"],
            payment_intent_id="pi_x", amount=1.0, currency="cad", dispute_id="dp_1",
            disputed_amount_cents=100, reason="fraudulent", dispute_status=status,
        ).model_dump(mode="json")

    await consumer.handle_payment_event(event(PaymentEvents.PAYMENT_DISPUTE_OPENED, "needs_response"))
    assert (await integration_client.get(f"{TEST_API}/orders/{order['id']}")).json()["dispute_status"] == "open"

    await consumer.handle_payment_event(event(PaymentEvents.PAYMENT_DISPUTE_CLOSED, "lost"))
    assert (await integration_client.get(f"{TEST_API}/orders/{order['id']}")).json()["dispute_status"] == "lost"


# ---------------------------------------------------------------- sales tax


async def _tax_the_order(db: TestDatabaseSessionManager, order_id: str, tax: Decimal) -> Order:
    """Give the confirmed order a tax line, as if Stripe Tax had priced it."""
    async with db.transaction() as session:
        order = await session.get(Order, UUID(order_id))
        order.tax_amount = tax
        order.amount = Decimal(order.subtotal_amount) + Decimal(order.shipping_amount or 0) + tax
        order.tax_calculation_id = "taxcalc_test"
        return order


async def test_a_refund_of_a_taxed_order_gives_back_its_share_of_the_tax(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    order = await _tax_the_order(test_database_session_manager, order_id, Decimal("5.00"))
    item_id, _, price = await _line(test_database_session_manager, order_id)
    base = Decimal(order.subtotal_amount) + Decimal(order.shipping_amount or 0)
    expected_tax = (Decimal("5.00") * price / base).quantize(Decimal("0.01"))

    response = await integration_client.post(
        _refunds_url(order_id), json={"lines": [{"order_item_id": item_id, "quantity": 1}], "reason": "print faded"}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(body["tax_amount"]) == expected_tax
    assert Decimal(body["amount"]) == price + expected_tax
    assert (await _refund_commands(test_database_session_manager))[0]["amount_cents"] == int((price + expected_tax) * 100)


async def test_refunding_everything_returns_exactly_the_tax_charged(
    integration_client: AsyncClient, queued_job: dict, test_database_session_manager  # noqa: F811
) -> None:
    """Per-refund rounding must not leave a cent of tax behind, or take one too many."""
    order_id = queued_job["order"]["id"]
    order = await _tax_the_order(test_database_session_manager, order_id, Decimal("3.33"))
    item_id, quantity, _ = await _line(test_database_session_manager, order_id)
    url = _refunds_url(order_id)

    refunds = [
        await integration_client.post(url, json={"lines": [{"order_item_id": item_id, "quantity": 1}], "reason": "one"})
    ]
    if quantity > 1:
        refunds.append(await integration_client.post(
            url, json={"lines": [{"order_item_id": item_id, "quantity": quantity - 1}], "reason": "rest"}
        ))
    if Decimal(order.shipping_amount or 0) > 0:
        refunds.append(await integration_client.post(url, json={"include_shipping": True, "reason": "shipping"}))

    assert all(r.status_code == 201 for r in refunds), [r.text for r in refunds]
    assert sum(Decimal(r.json()["tax_amount"]) for r in refunds) == Decimal("3.33")
    assert sum(Decimal(r.json()["amount"]) for r in refunds) == Decimal(order.amount)
