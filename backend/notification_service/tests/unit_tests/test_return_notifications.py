"""Return events: who is told, and what the emails say. Templates are the real ones; only SMTP is replaced."""

from logging import getLogger
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from uuid import uuid4

import pytest

from events_consumer.event_handlers import OrderEventHandler
from contracts.events import OrderReturnEvent, OrderReturnRefundedEvent
from contracts.returns import RefundedLineSummary, ReturnFault, ReturnLineSummary, ReturnReason
from email_service.email_service import AdminAlerts, OrderRelatedNotifications
from contracts.event_enums import OrderEvents
from settings import get_settings
from tests.unit_tests.test_event_handlers import _make_handler

TASK_MODULE = "events_consumer.event_handlers"


def _event(event_type: str, **overrides) -> OrderReturnEvent:
    values = dict(
        event_type=event_type, order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
        return_id=uuid4(), reason=ReturnReason.DEFECTIVE, fault=ReturnFault.SELLER,
        description="Seam split on first wash",
        lines=[
            ReturnLineSummary(product_name="Custom Tee", quantity=1, ships_back=False),
            ReturnLineSummary(product_name="Hoodie", quantity=2, ships_back=True),
        ],
        photo_count=2,
    )
    return OrderReturnEvent(**{**values, **overrides})


def _sent_body(service) -> str:
    return str(service.fast_mail.send_message.await_args.args[0].body)


# ------------------------------------------------------------------ handler


async def test_a_request_alerts_the_admin_and_tells_the_customer() -> None:
    handler = _make_handler(OrderEventHandler)
    message = _event(OrderEvents.RETURN_REQUESTED).model_dump(mode="json")

    with patch(f"{TASK_MODULE}.send_admin_return_alert") as alert, \
            patch(f"{TASK_MODULE}.send_return_requested_email") as confirmation:
        alert.kiq = AsyncMock()
        confirmation.kiq = AsyncMock()
        await handler.handle(message)

    alert.kiq.assert_awaited_once_with(message)
    confirmation.kiq.assert_awaited_once_with(message)
    assert "received your return request" in handler._save_notification.await_args.kwargs["message"]


def _refunded(**overrides) -> OrderReturnRefundedEvent:
    values = dict(
        order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
        return_id=uuid4(), refund_id=uuid4(), amount=Decimal("41.31"), includes_shipping=True,
        lines=[RefundedLineSummary(product_name="Hoodie", quantity=2, amount=Decimal("30.99"))],
    )
    return OrderReturnRefundedEvent(**{**values, **overrides})


async def test_a_return_refund_is_emailed_without_a_second_in_app_notice() -> None:
    handler = _make_handler(OrderEventHandler)
    message = _refunded().model_dump(mode="json")

    with patch(f"{TASK_MODULE}.send_return_refunded_email") as task:
        task.kiq = AsyncMock()
        await handler.handle(message)

    task.kiq.assert_awaited_once_with(message)
    # payment.refunded for the same refund already tells the customer in-app.
    handler._save_notification.assert_not_awaited()


@pytest.mark.parametrize("event_type", [OrderEvents.RETURN_APPROVED, OrderEvents.RETURN_REJECTED])
async def test_a_decision_is_emailed_to_the_customer(event_type: str) -> None:
    handler = _make_handler(OrderEventHandler)
    message = _event(event_type, admin_note="ok").model_dump(mode="json")

    with patch(f"{TASK_MODULE}.send_return_decision_email") as task:
        task.kiq = AsyncMock()
        await handler.handle(message)

    task.kiq.assert_awaited_once_with(message)
    assert handler._save_notification.await_args.kwargs["user_id"] is not None


# ------------------------------------------------------------------- emails


async def test_the_admin_alert_escapes_what_the_customer_wrote(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ADMIN_ALERT_EMAIL", "ops@example.com")
    alerts = AdminAlerts(settings=settings, logger=getLogger("test"))
    alerts.fast_mail.send_message = AsyncMock()

    await alerts.send_return_alert(_event(
        OrderEvents.RETURN_REQUESTED, description='<a href="https://evil.example">click</a>'
    ))

    body = _sent_body(alerts)
    assert "Custom Tee" in body and "(no need to send back)" in body and "Photos attached: 2" in body
    assert '<a href="https://evil.example">' not in body
    assert "&lt;a href=" in body


async def test_without_an_admin_address_the_request_is_only_logged(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ADMIN_ALERT_EMAIL", None)
    alerts = AdminAlerts(settings=settings, logger=getLogger("test"))
    alerts.fast_mail.send_message = AsyncMock()

    await alerts.send_return_alert(_event(OrderEvents.RETURN_REQUESTED))

    alerts.fast_mail.send_message.assert_not_awaited()


async def test_an_approval_says_what_to_keep_and_where_to_post_the_rest() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    event = _event(OrderEvents.RETURN_APPROVED, return_address="Returns, 1 Main St, Calgary AB")
    await notifications.send_return_decision(event)

    body = _sent_body(notifications)
    message = notifications.fast_mail.send_message.await_args.args[0]
    assert "approved" in message.subject
    assert "You don't need to send back" in body and "Custom Tee" in body
    assert "2 x Hoodie" in body and "Returns, 1 Main St, Calgary AB" in body
    # Our fault: the customer's postage is refunded.
    assert "we refund it" in body
    # The account emails' layout, with a link to the order's page.
    assert 'class="container"' in body
    assert f"/order/{event.order_id}" in body


async def test_a_change_of_mind_approval_leaves_postage_with_the_customer() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    await notifications.send_return_decision(_event(
        OrderEvents.RETURN_APPROVED, reason=ReturnReason.CHANGED_MIND, fault=ReturnFault.CUSTOMER,
        lines=[ReturnLineSummary(product_name="Hoodie", quantity=1, ships_back=True)],
    ))

    body = _sent_body(notifications)
    assert "Return postage is at your cost" in body
    assert "support team will email you the return address" in body


async def test_a_rejection_carries_the_reason() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    event = _event(OrderEvents.RETURN_REJECTED, admin_note="Worn and washed")
    await notifications.send_return_decision(event)

    message = notifications.fast_mail.send_message.await_args.args[0]
    body = _sent_body(notifications)
    assert "not accepted" in message.subject
    assert "Worn and washed" in body
    assert f"/order/{event.order_id}" in body


async def test_the_request_confirmation_says_what_happens_next() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()
    event = _event(OrderEvents.RETURN_REQUESTED, reason=ReturnReason.DAMAGED)

    await notifications.send_return_requested(event)

    message = notifications.fast_mail.send_message.await_args.args[0]
    body = _sent_body(notifications)
    assert [recipient.email for recipient in message.recipients] == ["buyer@example.com"]
    assert "received your return request" in message.subject
    assert "1 x Custom Tee" in body and "2 x Hoodie" in body
    assert "It arrived damaged" in body
    assert "Please don't send anything back until then" in body
    # Our fault: refunded in full if approved.
    assert "refunded in full, shipping included" in body
    assert f"/order/{event.order_id}" in body and 'class="container"' in body


async def test_a_change_of_mind_request_warns_about_postage() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    await notifications.send_return_requested(
        _event(OrderEvents.RETURN_REQUESTED, reason=ReturnReason.DOES_NOT_FIT, fault=ReturnFault.CUSTOMER)
    )

    body = _sent_body(notifications)
    assert "It does not fit" in body
    assert "original shipping is not refunded" in body


async def test_the_refund_email_states_the_amount_and_the_lines() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()
    event = _refunded()

    await notifications.send_return_refunded(event)

    message = notifications.fast_mail.send_message.await_args.args[0]
    body = _sent_body(notifications)
    assert [recipient.email for recipient in message.recipients] == ["buyer@example.com"]
    assert "refund" in message.subject
    assert "41.31 CAD" in body and "2 x Hoodie (30.99 CAD)" in body
    assert "<li>Shipping</li>" in body
    assert f"/order/{event.order_id}" in body


async def test_a_refund_without_shipping_does_not_list_it() -> None:
    notifications = OrderRelatedNotifications(settings=get_settings(), logger=getLogger("test"))
    notifications.fast_mail.send_message = AsyncMock()

    await notifications.send_return_refunded(_refunded(includes_shipping=False))

    assert "<li>Shipping</li>" not in _sent_body(notifications)
