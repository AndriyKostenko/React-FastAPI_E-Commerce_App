"""
Every event order-service writes to its outbox must have a way out.

A written event with no route is retried forever and never published: that is
how the partial-refund command sat in the outbox without ever reaching
payment-service. The guard below reads the event types the code writes and
checks each one routes to a publisher.
"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from events_publisher.order_event_publisher import OrderEventPublisher
from service_layer.outbox_poller_service import route_order_event
from shared.contracts.events import PaymentRefundRequested
from shared.enums import event_enums
from shared.enums.event_enums import PaymentCommands, ProductionEvents

SERVICE_ROOT = Path(__file__).resolve().parents[2]
WRITTEN = re.compile(r"add_outbox_event\(\s*event_type=(\w+)\.(\w+)")

# Written through a variable rather than a literal, so listed by hand.
WRITTEN_DYNAMICALLY = [
    *ProductionEvents,  # production_queue_service publishes each job transition
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
    publisher = MagicMock(spec=OrderEventPublisher)
    for name in dir(OrderEventPublisher):
        if name.startswith("publish_"):
            setattr(publisher, name, AsyncMock())
    return publisher


def test_the_guard_sees_the_refund_command() -> None:
    assert PaymentCommands.REFUND_REQUESTED in _written_event_types()


@pytest.mark.parametrize("event_type", sorted(_written_event_types()))
async def test_every_written_event_type_is_routed(event_type: str) -> None:
    await route_order_event(event_type, {}, _publisher())


async def test_a_refund_command_goes_to_payment_service() -> None:
    publisher = OrderEventPublisher.__new__(OrderEventPublisher)
    publisher.logger = MagicMock()
    publisher.order_exchange = MagicMock(name="order_exchange")
    publisher.publish_an_event = AsyncMock()
    command = PaymentRefundRequested(
        order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
        refund_id=uuid4(), amount_cents=1999, reason="Return: defective",
    )

    await route_order_event(PaymentCommands.REFUND_REQUESTED, command.model_dump(mode="json"), publisher)

    sent = publisher.publish_an_event.await_args.kwargs
    # payment-service's command queue binds "payment.*.requested" on the order exchange.
    assert sent["routing_key"] == "payment.refund.requested"
    assert sent["exchange"] is publisher.order_exchange
    assert sent["event"].refund_id == command.refund_id and sent["event"].amount_cents == 1999
