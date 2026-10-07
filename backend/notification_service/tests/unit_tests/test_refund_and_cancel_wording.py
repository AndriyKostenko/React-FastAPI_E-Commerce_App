"""What the customer reads: refund notices by scope, and the order-cancelled email (real template, SMTP replaced)."""

from logging import getLogger
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from events_consumer.event_handlers import PaymentEventHandler
from shared.contracts.events import OrderCancelledEvent, PaymentRefundedEvent, RefundScope
from shared.email_service.email_service import OrderRelatedNotifications
from shared.settings import get_settings
from tests.unit_tests.test_event_handlers import _make_handler

ORDER_ID = uuid4()


def _refunded(**overrides: object) -> PaymentRefundedEvent:
    values: dict[str, object] = dict(
        order_id=ORDER_ID, user_id=uuid4(), user_email="buyer@example.com", payment_intent_id="pi_test",
        amount=3127, currency="cad", refund_id=uuid4(), refunded_amount_cents=3127,
    )
    return PaymentRefundedEvent(**{**values, **overrides})


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (RefundScope.WHOLE, "was refunded in full (31.27 CAD)"),
        (RefundScope.REST, "The rest of your payment"),
        (RefundScope.PART, "Part of your payment"),
    ],
)
async def test_the_refund_notice_says_how_much_of_the_payment_went_back(scope: RefundScope, expected: str) -> None:
    handler = _make_handler(PaymentEventHandler)

    await handler.handle(_refunded(refund_scope=scope).model_dump(mode="json"))

    assert expected in handler._save_notification.await_args.kwargs["message"]


async def test_an_event_from_before_the_scope_keeps_the_old_wording() -> None:
    handler = _make_handler(PaymentEventHandler)

    await handler.handle(_refunded(refund_scope=None, refund_id=None).model_dump(mode="json"))

    assert handler._save_notification.await_args.kwargs["message"] == f"Payment for order #{ORDER_ID} was refunded."


def _cancelled(**overrides: object) -> OrderCancelledEvent:
    values: dict[str, object] = dict(
        order_id=ORDER_ID, user_id=uuid4(), user_email="buyer@example.com",
        reason="CJ did not accept the order within 24 hours",
    )
    return OrderCancelledEvent(**{**values, **overrides})


async def _send(event: OrderCancelledEvent) -> tuple[str, str]:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()
    await notifications.send_order_cancelled_notification(event)
    message = notifications.fast_mail.send_message.await_args.args[0]
    return message.subject, str(message.body)


async def test_the_cancellation_email_says_why_and_what_happens_to_the_money() -> None:
    subject, body = await _send(_cancelled())

    assert subject == f"Your order {ORDER_ID} was cancelled" and "Refund Initiated" not in subject
    assert str(ORDER_ID) in body and "CJ did not accept the order within 24 hours" in body
    assert "hold is released" in body and "will contact you" not in body


async def test_goods_already_made_promise_no_automatic_refund() -> None:
    _, body = await _send(_cancelled(reconciliation_required=True))

    assert "not refunding it" in body and "will contact you" in body
    assert "hold is released" not in body
