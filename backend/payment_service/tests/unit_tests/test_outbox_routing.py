"""
Every event payment-service writes to its outbox must have a way out.

A written event with no route is retried forever and never published. That is
how a refund Stripe refused stayed "requested" in order-service, and how no
dispute ever reached an admin. The guard reads the event types the code writes
and checks each one routes to a publisher (order-service has the same guard).
"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from events_publisher.payment_event_publisher import PaymentEventPublisher
from service_layer.outbox_poller_service import route_payment_event
from shared.contracts.events import PaymentRefundFailedEvent
from shared.enums import event_enums
from shared.enums.event_enums import PaymentEvents

SERVICE_ROOT = Path(__file__).resolve().parents[2]
WRITTEN = re.compile(r"add_outbox_event\(\s*event_type=(\w+)\.(\w+)")

# Written through a variable rather than a literal, so listed by hand.
WRITTEN_DYNAMICALLY = [
    PaymentEvents.PAYMENT_DISPUTE_OPENED,  # payment_dispute_service passes the type it was given
    PaymentEvents.PAYMENT_DISPUTE_CLOSED,
]


def _written_event_types() -> set[str]:
    found: set[str] = set(WRITTEN_DYNAMICALLY)
    for path in SERVICE_ROOT.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        for enum_name, member in WRITTEN.findall(path.read_text()):
            found.add(getattr(getattr(event_enums, enum_name), member))
    return found


def _publisher() -> MagicMock:
    publisher = MagicMock(spec=PaymentEventPublisher)
    for name in dir(PaymentEventPublisher):
        if name.startswith("publish_"):
            setattr(publisher, name, AsyncMock())
    return publisher


def test_the_guard_sees_the_refund_failure() -> None:
    assert PaymentEvents.PAYMENT_REFUND_FAILED in _written_event_types()


@pytest.mark.parametrize("event_type", sorted(_written_event_types()))
async def test_every_written_event_type_is_routed(event_type: str) -> None:
    await route_payment_event(event_type, {}, _publisher())


async def test_a_refused_refund_reaches_order_service() -> None:
    publisher = PaymentEventPublisher.__new__(PaymentEventPublisher)
    publisher.logger = MagicMock()
    publisher.payment_exchange = MagicMock(name="payment_exchange")
    publisher.publish_an_event = AsyncMock()
    event = PaymentRefundFailedEvent(
        order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com", payment_intent_id="pi_test",
        amount=4_873, currency="cad", refund_id=uuid4(), reason="payment is refunded; nothing can be refunded",
    )

    await route_payment_event(PaymentEvents.PAYMENT_REFUND_FAILED, event.model_dump(mode="json"), publisher)

    assert publisher.publish_an_event.await_args is not None
    sent = publisher.publish_an_event.await_args.kwargs
    # order-service's payment queue binds "payment.*" on the payment exchange.
    assert sent["routing_key"] == "payment.refund_failed" and sent["routing_key"].count(".") == 1
    assert sent["exchange"] is publisher.payment_exchange
    assert sent["event"].refund_id == event.refund_id
