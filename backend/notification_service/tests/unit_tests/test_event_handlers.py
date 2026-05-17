"""Unit tests for UserEventHandler, OrderEventHandler, and PaymentEventHandler."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from events_consumer.event_handlers import (
    UserEventHandler,
    OrderEventHandler,
    PaymentEventHandler,
)
from tests.constants import TEST_USER_ID, TEST_ORDER_ID, TEST_EMAIL, TEST_EVENT_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(cls):
    """Create a handler with fully-mocked infrastructure."""
    handler = cls(
        idempotency_service=MagicMock(),
        db_session_manager=MagicMock(),
        logger=MagicMock(),
    )
    handler._try_claim = AsyncMock(return_value=True)
    handler._release_claim = AsyncMock()
    handler._mark_processed = AsyncMock()
    handler._save_notification = AsyncMock()
    return handler


def _user_msg(event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "event_id": TEST_EVENT_ID,
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
    }


def _order_msg(event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "event_id": TEST_EVENT_ID,
        "order_id": str(TEST_ORDER_ID),
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "reason": "Customer requested cancellation",
    }


def _payment_msg(event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "event_id": TEST_EVENT_ID,
        "order_id": str(TEST_ORDER_ID),
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "reason": "Insufficient funds",
        "amount": 99.99,
        "currency": "USD",
        "payment_intent_id": "pi_test_123",
    }


# ---------------------------------------------------------------------------
# UserEventHandler
# ---------------------------------------------------------------------------

TASK_MODULE = "events_consumer.event_handlers"


class TestUserEventHandlerRegistered:
    async def test_dispatches_verification_email_task(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.registered")

        with patch(f"{TASK_MODULE}.send_verification_email") as mock_task:
            mock_task.kiq = AsyncMock()
            await handler.handle(msg)

        mock_task.kiq.assert_awaited_once_with(msg)
        handler._save_notification.assert_awaited_once()
        handler._mark_processed.assert_awaited_once()

    async def test_skips_duplicate_event(self):
        handler = _make_handler(UserEventHandler)
        handler._try_claim = AsyncMock(return_value=False)
        msg = _user_msg("user.registered")

        with patch(f"{TASK_MODULE}.send_verification_email") as mock_task:
            mock_task.kiq = AsyncMock()
            await handler.handle(msg)

        mock_task.kiq.assert_not_awaited()
        handler._save_notification.assert_not_awaited()
        handler._mark_processed.assert_not_awaited()


class TestUserEventHandlerEmailVerified:
    async def test_dispatches_email_verified_task(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.email.verified")

        with patch(f"{TASK_MODULE}.send_email_verified_notification") as mock_task:
            mock_task.kiq = AsyncMock()
            await handler.handle(msg)

        mock_task.kiq.assert_awaited_once_with(msg)
        handler._save_notification.assert_awaited_once()


class TestUserEventHandlerLoggedIn:
    async def test_dispatches_login_notification_task(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.logged.in")

        with patch(f"{TASK_MODULE}.send_login_notification") as mock_task:
            mock_task.kiq = AsyncMock()
            await handler.handle(msg)

        mock_task.kiq.assert_awaited_once_with(msg)
        handler._save_notification.assert_awaited_once()


class TestUserEventHandlerPasswordResetRequest:
    async def test_dispatches_password_reset_email_task(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.password.reset.request")

        with patch(f"{TASK_MODULE}.send_password_reset_email") as mock_task:
            mock_task.kiq = AsyncMock()
            await handler.handle(msg)

        mock_task.kiq.assert_awaited_once_with(msg)
        handler._save_notification.assert_awaited_once()


class TestUserEventHandlerPasswordResetSuccess:
    async def test_dispatches_password_reset_success_task(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.password.reset.success")

        with patch(f"{TASK_MODULE}.send_password_reset_success") as mock_task:
            mock_task.kiq = AsyncMock()
            await handler.handle(msg)

        mock_task.kiq.assert_awaited_once_with(msg)
        handler._save_notification.assert_awaited_once()


class TestUserEventHandlerUnknownType:
    async def test_unhandled_type_skips_save_and_mark(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.unknown.event")

        await handler.handle(msg)

        handler._save_notification.assert_not_awaited()
        handler._mark_processed.assert_not_awaited()

    async def test_releases_claim_on_exception(self):
        handler = _make_handler(UserEventHandler)
        msg = _user_msg("user.registered")

        with patch(f"{TASK_MODULE}.send_verification_email") as mock_task:
            mock_task.kiq = AsyncMock(side_effect=RuntimeError("broker down"))
            with pytest.raises(RuntimeError):
                await handler.handle(msg)

        handler._release_claim.assert_awaited_once()
        handler._mark_processed.assert_not_awaited()


# ---------------------------------------------------------------------------
# OrderEventHandler
# ---------------------------------------------------------------------------

class TestOrderEventHandlerCreated:
    async def test_order_created_marks_processed_as_skipped_and_no_save(self):
        handler = _make_handler(OrderEventHandler)
        msg = _order_msg("order.created")

        await handler.handle(msg)

        handler._save_notification.assert_not_awaited()
        handler._mark_processed.assert_awaited_once()
        _, kwargs = handler._mark_processed.call_args
        assert kwargs.get("result") == "skipped"


class TestOrderEventHandlerConfirmed:
    async def test_sends_confirmed_email_and_saves(self):
        handler = _make_handler(OrderEventHandler)
        msg = _order_msg("order.confirmed")

        with patch(f"{TASK_MODULE}.order_notification_email_service") as mock_email:
            mock_email.send_order_confirmed_notification = AsyncMock()
            await handler.handle(msg)

        mock_email.send_order_confirmed_notification.assert_awaited_once()
        handler._save_notification.assert_awaited_once()
        handler._mark_processed.assert_awaited_once()

    async def test_skips_duplicate_confirmed_event(self):
        handler = _make_handler(OrderEventHandler)
        handler._try_claim = AsyncMock(return_value=False)
        msg = _order_msg("order.confirmed")

        with patch(f"{TASK_MODULE}.order_notification_email_service") as mock_email:
            mock_email.send_order_confirmed_notification = AsyncMock()
            await handler.handle(msg)

        mock_email.send_order_confirmed_notification.assert_not_awaited()
        handler._save_notification.assert_not_awaited()


class TestOrderEventHandlerCancelled:
    async def test_sends_cancelled_email_and_saves(self):
        handler = _make_handler(OrderEventHandler)
        msg = _order_msg("order.cancelled")

        with patch(f"{TASK_MODULE}.order_notification_email_service") as mock_email:
            mock_email.send_order_cancelled_notification = AsyncMock()
            await handler.handle(msg)

        mock_email.send_order_cancelled_notification.assert_awaited_once()
        handler._save_notification.assert_awaited_once()
        handler._mark_processed.assert_awaited_once()


class TestOrderEventHandlerUnknownType:
    async def test_unhandled_type_marks_skipped_and_no_save(self):
        handler = _make_handler(OrderEventHandler)
        msg = _order_msg("order.shipped")

        await handler.handle(msg)

        handler._save_notification.assert_not_awaited()
        handler._mark_processed.assert_awaited_once()
        _, kwargs = handler._mark_processed.call_args
        assert kwargs.get("result") == "skipped"


# ---------------------------------------------------------------------------
# PaymentEventHandler
# ---------------------------------------------------------------------------

class TestPaymentEventHandlerSucceeded:
    async def test_saves_notification_for_succeeded(self):
        handler = _make_handler(PaymentEventHandler)
        msg = _payment_msg("payment.succeeded")

        await handler.handle(msg)

        handler._save_notification.assert_awaited_once()
        handler._mark_processed.assert_awaited_once()

    async def test_skips_duplicate_succeeded_event(self):
        handler = _make_handler(PaymentEventHandler)
        handler._try_claim = AsyncMock(return_value=False)
        msg = _payment_msg("payment.succeeded")

        await handler.handle(msg)

        handler._save_notification.assert_not_awaited()
        handler._mark_processed.assert_not_awaited()


class TestPaymentEventHandlerFailed:
    async def test_saves_notification_with_reason(self):
        handler = _make_handler(PaymentEventHandler)
        msg = _payment_msg("payment.failed")

        await handler.handle(msg)

        handler._save_notification.assert_awaited_once()
        call_kwargs = handler._save_notification.call_args.kwargs
        assert "Insufficient funds" in call_kwargs["message"]


class TestPaymentEventHandlerRefunded:
    async def test_saves_notification_for_refunded(self):
        handler = _make_handler(PaymentEventHandler)
        msg = _payment_msg("payment.refunded")

        await handler.handle(msg)

        handler._save_notification.assert_awaited_once()
        handler._mark_processed.assert_awaited_once()


class TestPaymentEventHandlerCancelled:
    async def test_saves_notification_with_reason(self):
        handler = _make_handler(PaymentEventHandler)
        msg = _payment_msg("payment.cancelled")

        await handler.handle(msg)

        handler._save_notification.assert_awaited_once()
        call_kwargs = handler._save_notification.call_args.kwargs
        assert "Insufficient funds" in call_kwargs["message"]


class TestPaymentEventHandlerUnknownType:
    async def test_unhandled_type_marks_skipped_no_save(self):
        handler = _make_handler(PaymentEventHandler)
        msg = _payment_msg("payment.unknown")

        await handler.handle(msg)

        handler._save_notification.assert_not_awaited()
        handler._mark_processed.assert_awaited_once()
        _, kwargs = handler._mark_processed.call_args
        assert kwargs.get("result") == "skipped"

    async def test_releases_claim_on_exception(self):
        handler = _make_handler(PaymentEventHandler)
        handler._save_notification = AsyncMock(side_effect=RuntimeError("db down"))
        msg = _payment_msg("payment.succeeded")

        with pytest.raises(RuntimeError):
            await handler.handle(msg)

        handler._release_claim.assert_awaited_once()
