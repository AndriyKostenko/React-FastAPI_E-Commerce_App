"""A cancelled print job: who is told, and what the email says. The template is the real one; only SMTP is replaced."""

from decimal import Decimal
from logging import getLogger
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from events_consumer.event_handlers import ProductionEventHandler
from shared.contracts.events import ProductionJobCancelledEvent
from shared.email_service.email_service import OrderRelatedNotifications
from shared.settings import get_settings
from tests.unit_tests.test_event_handlers import _make_handler

TASK_MODULE = "events_consumer.event_handlers"


def _event(**overrides: object) -> ProductionJobCancelledEvent:
    values: dict[str, object] = dict(
        order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com", job_id=uuid4(),
        order_item_id=uuid4(), quantity=1, product_name="Custom T-Shirt (M)",
        reason="Out of white M blanks", refunded_amount=Decimal("31.27"), shipping_refunded=True,
    )
    return ProductionJobCancelledEvent(**{**values, **overrides})


def _sent_body(service: OrderRelatedNotifications) -> str:
    return str(service.fast_mail.send_message.await_args.args[0].body)


async def test_a_refunded_cancellation_is_emailed_to_the_customer() -> None:
    handler = _make_handler(ProductionEventHandler)
    message = _event().model_dump(mode="json")

    with patch(f"{TASK_MODULE}.send_production_job_cancelled_email") as task:
        task.kiq = AsyncMock()
        await handler.handle(message)

    task.kiq.assert_awaited_once_with(message)
    saved = handler._save_notification.await_args.kwargs
    assert saved["user_id"] is not None and "cancelled before printing" in saved["message"]


async def test_a_cancellation_left_to_a_human_tells_the_customer_nothing() -> None:
    handler = _make_handler(ProductionEventHandler)
    message = _event(reconciliation_required=True, refunded_amount=None, shipping_refunded=False).model_dump(mode="json")

    with patch(f"{TASK_MODULE}.send_production_job_cancelled_email") as task:
        task.kiq = AsyncMock()
        await handler.handle(message)

    task.kiq.assert_not_awaited()
    handler._save_notification.assert_not_awaited()


async def test_the_email_states_the_refund_and_the_shipping() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    await notifications.send_production_job_cancelled(_event())

    body = _sent_body(notifications)
    assert "Custom T-Shirt (M)" in body and "Out of white M blanks" in body
    assert "31.27 CAD" in body and "shipping included" in body


async def test_a_line_refund_without_shipping_does_not_claim_it() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    await notifications.send_production_job_cancelled(_event(refunded_amount=Decimal("21.28"), shipping_refunded=False))

    body = _sent_body(notifications)
    assert "21.28 CAD" in body and "shipping included" not in body
