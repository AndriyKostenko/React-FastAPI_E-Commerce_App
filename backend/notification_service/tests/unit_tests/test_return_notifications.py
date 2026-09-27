"""Return events: who is told, and what the emails say. Templates are the real ones; only SMTP is replaced."""

from logging import getLogger
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from events_consumer.event_handlers import OrderEventHandler
from shared.contracts.events import OrderReturnEvent
from shared.contracts.returns import ReturnFault, ReturnLineSummary, ReturnReason
from shared.email_service.email_service import AdminAlerts, OrderRelatedNotifications
from shared.enums.event_enums import OrderEvents
from shared.settings import get_settings
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


async def test_a_request_alerts_the_admin_and_tells_the_customer_in_app() -> None:
    handler = _make_handler(OrderEventHandler)
    message = _event(OrderEvents.RETURN_REQUESTED).model_dump(mode="json")

    with patch(f"{TASK_MODULE}.send_admin_return_alert") as task:
        task.kiq = AsyncMock()
        await handler.handle(message)

    task.kiq.assert_awaited_once_with(message)
    assert "received your return request" in handler._save_notification.await_args.kwargs["message"]


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

    await notifications.send_return_decision(_event(
        OrderEvents.RETURN_APPROVED, return_address="Returns, 1 Main St, Calgary AB"
    ))

    body = _sent_body(notifications)
    message = notifications.fast_mail.send_message.await_args.args[0]
    assert "approved" in message.subject
    assert "You don't need to send back" in body and "Custom Tee" in body
    assert "2 x Hoodie" in body and "Returns, 1 Main St, Calgary AB" in body
    # Our fault: the customer's postage is refunded.
    assert "we refund it" in body


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

    await notifications.send_return_decision(_event(OrderEvents.RETURN_REJECTED, admin_note="Worn and washed"))

    message = notifications.fast_mail.send_message.await_args.args[0]
    assert "not accepted" in message.subject
    assert "Worn and washed" in _sent_body(notifications)
