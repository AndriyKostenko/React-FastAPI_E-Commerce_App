"""
Every link an email carries must open a real frontend page. Templates are the
real ones; only SMTP is replaced, and the sent HTML is searched for each href.
"""

import re
from logging import getLogger
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.contracts.events import (
    EmailVerificationEvent,
    OrderCreatedEvent,
    OrderDeliveredBaseEvent,
    PasswordResetRequestedEvent,
    PasswordResetSuccessEvent,
    UserRegisteredEvent,
)
from shared.email_service.email_links import EmailLinks
from shared.email_service.email_service import OrderRelatedNotifications, UserRelatedNotifications
from shared.settings import get_settings

FRONTEND = "http://localhost:30000"
TOKEN = "tok_" + "a" * 40
# Pages the frontend actually serves (frontend/app/**/page.tsx).
FRONTEND_ROUTES = (
    re.compile(r"/activate"),
    re.compile(r"/password-reset"),
    re.compile(r"/login"),
    re.compile(r"/order/[0-9a-f-]{36}"),
)


@pytest.fixture
def settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "FRONTEND_URL", FRONTEND)
    return settings


def _hrefs(service) -> list[str]:
    body = str(service.fast_mail.send_message.await_args.args[0].body)
    return re.findall(r'href="([^"]+)"', body)


def _assert_opens_a_page(href: str) -> None:
    assert href.startswith(FRONTEND + "/"), f"{href} is not a frontend URL"
    path = href[len(FRONTEND):].split("#", 1)[0]
    assert any(route.fullmatch(path) for route in FRONTEND_ROUTES), f"no page serves {path}"


# ------------------------------------------------------------------ builder


def test_tokens_travel_in_the_fragment_never_the_path() -> None:
    links = EmailLinks(FRONTEND + "/")

    assert links.activation(TOKEN) == f"{FRONTEND}/activate#token={TOKEN}"
    assert links.password_reset(TOKEN) == f"{FRONTEND}/password-reset#token={TOKEN}"


def test_a_token_cannot_break_out_of_the_fragment() -> None:
    assert EmailLinks(FRONTEND).activation("a&b c/d") == f"{FRONTEND}/activate#token=a%26b%20c%2Fd"


def test_order_links_use_the_singular_frontend_route() -> None:
    order_id = uuid4()
    assert EmailLinks(FRONTEND).order(order_id) == f"{FRONTEND}/order/{order_id}"


# ------------------------------------------------------------------ emails


@pytest.mark.parametrize(
    ("send", "event", "expected"),
    [
        ("send_verification_email", UserRegisteredEvent(user_email="a@example.com", token=TOKEN),
         f"{FRONTEND}/activate#token={TOKEN}"),
        ("send_password_reset_email", PasswordResetRequestedEvent(user_email="a@example.com", reset_token=TOKEN),
         f"{FRONTEND}/password-reset#token={TOKEN}"),
        ("send_email_verified_notification", EmailVerificationEvent(user_email="a@example.com"),
         f"{FRONTEND}/login"),
        ("send_password_reset_success_email", PasswordResetSuccessEvent(user_email="a@example.com"),
         f"{FRONTEND}/login"),
    ],
    ids=["verification", "password-reset", "email-verified", "reset-done"],
)
async def test_account_emails_link_to_frontend_pages(settings, send: str, event, expected: str) -> None:
    service = UserRelatedNotifications(settings, getLogger("t"))
    service.fast_mail.send_message = AsyncMock()

    await getattr(service, send)(event)

    hrefs = _hrefs(service)
    assert expected in hrefs
    for href in hrefs:
        _assert_opens_a_page(href)


async def test_order_emails_link_to_the_order_page(settings) -> None:
    service = OrderRelatedNotifications(settings, getLogger("t"))
    service.fast_mail.send_message = AsyncMock()
    order_id = uuid4()

    await service.send_order_created_notification(
        OrderCreatedEvent(service="order-service", order_id=order_id, user_id=uuid4(),
                          user_email="a@example.com", items=[], total_amount=10.0)
    )

    assert _hrefs(service) == [f"{FRONTEND}/order/{order_id}"]


async def test_the_delivered_email_offers_support_by_reply(settings) -> None:
    """There is no support page; 'Let us know' writes to the shop's mailbox instead."""
    service = OrderRelatedNotifications(settings, getLogger("t"))
    service.fast_mail.send_message = AsyncMock()
    order_id = uuid4()

    await service.send_order_delivered_notification(
        OrderDeliveredBaseEvent(service="order-service", event_type="order.delivered",
                                order_id=order_id, user_id=uuid4(), user_email="a@example.com")
    )

    assert _hrefs(service) == [f"{FRONTEND}/order/{order_id}", f"mailto:{settings.MAIL_FROM}"]
