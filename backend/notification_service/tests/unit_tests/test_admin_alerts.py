"""The dispute alert renders from its real template; only SMTP is replaced."""

from datetime import UTC, datetime
from logging import getLogger
from unittest.mock import AsyncMock
from uuid import uuid4

from shared.contracts.events import PaymentDisputeEvent
from shared.email_service.email_service import AdminAlerts
from shared.settings import get_settings


def _event() -> PaymentDisputeEvent:
    return PaymentDisputeEvent(
        event_type="payment.dispute_opened", order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com",
        payment_intent_id="pi_1", amount=73.22, currency="cad", dispute_id="dp_1",
        disputed_amount_cents=7322, reason="fraudulent", dispute_status="needs_response",
        evidence_due_by=datetime(2026, 10, 9, tzinfo=UTC),
    )


async def test_the_alert_is_rendered_and_sent_to_the_admin(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ADMIN_ALERT_EMAIL", "ops@example.com")
    alerts = AdminAlerts(settings=settings, logger=getLogger("test"))
    alerts.fast_mail.send_message = AsyncMock()

    await alerts.send_dispute_alert(_event())

    message = alerts.fast_mail.send_message.await_args.args[0]
    assert [str(getattr(r, "email", r)) for r in message.recipients] == ["ops@example.com"]
    body = str(message.body)
    assert "dp_1" in body and "73.22 CAD" in body and "2026-10-09" in body


async def test_without_an_admin_address_nothing_is_sent(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ADMIN_ALERT_EMAIL", None)
    alerts = AdminAlerts(settings=settings, logger=getLogger("test"))
    alerts.fast_mail.send_message = AsyncMock()

    await alerts.send_dispute_alert(_event())

    alerts.fast_mail.send_message.assert_not_awaited()
