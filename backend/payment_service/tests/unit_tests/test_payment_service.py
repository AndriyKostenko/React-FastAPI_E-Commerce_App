"""
Unit tests for PaymentService.

All external dependencies (repository, Stripe, outbox service) are mocked
so every test runs without a live database or Stripe account.
"""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from exceptions.payment_exceptions import (
    PaymentNotFoundError,
    PaymentsNotFoundError,
    DuplicatePaymentIntentError,
    PaymentCreationError,
    PaymentAlreadyFinalizedError,
    StripePaymentIntentCreationError,
    PaymentRefundError,
    PaymentCaptureError,
)
from models.payment_models import Payment
from shared.enums.status_enums import PaymentStatus
import shared.outbox.relay as relay_module
from shared.outbox.relay import OutboxRelay


# ---------------------------------------------------------------------------
# create_payment_intent
# ---------------------------------------------------------------------------

class TestCreatePaymentIntent:
    async def test_releases_read_transaction_before_stripe_call(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = None
        mock_payment_repository.create.return_value = mock_payment_orm

        async def create_after_commit(*args, **kwargs):
            mock_payment_repository.session.commit.assert_awaited_once()
            return MagicMock(id="pi_after_commit", client_secret="secret")

        mock_stripe_client.v1.payment_intents.create_async.side_effect = (
            create_after_commit
        )

        await payment_service_unit.create_payment_intent(
            order_id=mock_payment_orm.order_id,
            user_id=mock_payment_orm.user_id,
            user_email=mock_payment_orm.user_email,
            amount=mock_payment_orm.amount,
            currency=mock_payment_orm.currency,
        )

    async def test_creates_new_intent_and_returns_dict(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        """Happy path: no existing payment → creates Stripe intent + DB record."""
        mock_payment_repository.get_by_field.return_value = None
        mock_payment_repository.create.return_value = mock_payment_orm

        result = await payment_service_unit.create_payment_intent(
            order_id=mock_payment_orm.order_id,
            user_id=mock_payment_orm.user_id,
            user_email=mock_payment_orm.user_email,
            amount=mock_payment_orm.amount,
            currency=mock_payment_orm.currency,
        )

        assert "client_secret" in result
        assert "stripe_payment_intent_id" in result
        assert "payment_id" in result
        mock_payment_repository.create.assert_awaited_once()

    async def test_returns_existing_pending_intent(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        """Idempotency: existing PENDING payment returns the same Stripe intent."""
        mock_payment_orm.status = PaymentStatus.PENDING
        mock_payment_repository.get_by_field.return_value = mock_payment_orm

        result = await payment_service_unit.create_payment_intent(
            order_id=mock_payment_orm.order_id,
            user_id=mock_payment_orm.user_id,
            user_email=mock_payment_orm.user_email,
            amount=mock_payment_orm.amount,
            currency=mock_payment_orm.currency,
        )

        assert result["stripe_payment_intent_id"] == mock_payment_orm.stripe_payment_intent_id
        mock_payment_repository.create.assert_not_awaited()

    async def test_updates_existing_failed_payment(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        """Retry: existing FAILED payment creates new Stripe intent and updates record."""
        mock_payment_orm.status = PaymentStatus.FAILED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm

        result = await payment_service_unit.create_payment_intent(
            order_id=mock_payment_orm.order_id,
            user_id=mock_payment_orm.user_id,
            user_email=mock_payment_orm.user_email,
            amount=mock_payment_orm.amount,
            currency=mock_payment_orm.currency,
        )

        assert "client_secret" in result
        mock_payment_repository.update_by_id.assert_awaited_once()
        mock_payment_repository.create.assert_not_awaited()

    async def test_raises_when_payment_already_finalized(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
    ) -> None:
        """SUCCEEDED payment cannot create another intent."""
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm

        with pytest.raises(PaymentAlreadyFinalizedError):
            await payment_service_unit.create_payment_intent(
                order_id=mock_payment_orm.order_id,
                user_id=mock_payment_orm.user_id,
                user_email=mock_payment_orm.user_email,
                amount=mock_payment_orm.amount,
                currency=mock_payment_orm.currency,
            )

    async def test_raises_when_stripe_fails(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        """Stripe error is wrapped in StripePaymentIntentCreationError."""
        from stripe import StripeError
        mock_payment_repository.get_by_field.return_value = None
        mock_stripe_client.v1.payment_intents.create_async.side_effect = StripeError("Network error")

        with pytest.raises(StripePaymentIntentCreationError):
            await payment_service_unit.create_payment_intent(
                order_id=uuid4(),
                user_id=uuid4(),
                user_email="fail@example.com",
                amount=500,
                currency="usd",
            )

    async def test_raises_on_duplicate_intent_db_error(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        """IntegrityError on DB insert raises DuplicatePaymentIntentError."""
        mock_payment_repository.get_by_field.return_value = None
        mock_payment_repository.create.side_effect = IntegrityError(
            statement=None, params=None, orig=Exception("unique constraint")
        )

        with pytest.raises(DuplicatePaymentIntentError):
            await payment_service_unit.create_payment_intent(
                order_id=uuid4(),
                user_id=uuid4(),
                user_email="dup@example.com",
                amount=1000,
                currency="usd",
            )


# ---------------------------------------------------------------------------
# handle_payment_intent_succeeded
# ---------------------------------------------------------------------------

class TestHandlePaymentIntentSucceeded:
    async def test_updates_status_to_succeeded_and_writes_outbox(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()

        stripe_event_data = {
            "object": {
                "id": mock_payment_orm.stripe_payment_intent_id,
                "metadata": {
                    "order_id": str(mock_payment_orm.order_id),
                    "user_id": str(mock_payment_orm.user_id),
                },
            }
        }
        await payment_service_unit.handle_payment_intent_succeeded(stripe_event_data)

        update_call = mock_payment_repository.update_by_id.call_args
        assert update_call[1]["data"]["status"] == PaymentStatus.SUCCEEDED

    async def test_raises_when_payment_not_found(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = None

        with pytest.raises(PaymentNotFoundError):
            await payment_service_unit.handle_payment_intent_succeeded({
                "object": {"id": "pi_unknown", "metadata": {}}
            })


# ---------------------------------------------------------------------------
# handle_payment_intent_failed
# ---------------------------------------------------------------------------

class TestHandlePaymentIntentFailed:
    async def test_decline_records_reason_but_keeps_payment_open_for_retry(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()

        failure_msg = "Your card was declined."
        stripe_event_data = {
            "object": {
                "id": mock_payment_orm.stripe_payment_intent_id,
                "metadata": {},
                "last_payment_error": {"message": failure_msg},
            }
        }
        await payment_service_unit.handle_payment_intent_failed(stripe_event_data)

        update_call = mock_payment_repository.update_by_id.call_args
        assert update_call[1]["data"] == {"failure_reason": failure_msg}
        # A decline cancels nothing downstream: the customer may try another card.
        mock_outbox_event_service.add_outbox_event.assert_not_awaited()

    async def test_raises_when_payment_not_found(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = None

        with pytest.raises(PaymentNotFoundError):
            await payment_service_unit.handle_payment_intent_failed({
                "object": {"id": "pi_unknown", "metadata": {}, "last_payment_error": {}}
            })


# ---------------------------------------------------------------------------
# handle_payment_refund
# ---------------------------------------------------------------------------

class TestHandlePaymentRefund:
    async def test_releases_read_transaction_before_stripe_refund(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()

        async def refund_after_commit(*args, **kwargs):
            mock_payment_repository.session.commit.assert_awaited_once()
            return MagicMock(id="re_after_commit")

        mock_stripe_client.v1.refunds.create_async.side_effect = refund_after_commit

        await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)

    async def test_issues_refund_and_updates_status(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()

        result = await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)

        mock_stripe_client.v1.refunds.create_async.assert_awaited_once_with(
            {"payment_intent": mock_payment_orm.stripe_payment_intent_id},
            options={
                "idempotency_key": f"payment_refund:create:{mock_payment_orm.order_id}"
            },
        )
        update_call = mock_payment_repository.update_by_id.call_args
        assert update_call[1]["data"]["status"] == PaymentStatus.REFUNDED
        assert result is not None

    async def test_returns_none_when_no_payment_record(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = None

        result = await payment_service_unit.handle_payment_refund(uuid4())
        assert result is None

    async def test_skips_refund_for_non_succeeded_status(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.FAILED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm

        result = await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)

        assert result == mock_payment_orm

    async def test_raises_when_stripe_refund_fails(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        from stripe import StripeError
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_stripe_client.v1.refunds.create_async.side_effect = StripeError("Refund failed")

        with pytest.raises(PaymentRefundError):
            await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)

    async def test_pending_payment_reconciles_already_cancelled_stripe_intent(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        from stripe import StripeError

        mock_payment_orm.status = PaymentStatus.PENDING
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()
        mock_stripe_client.v1.payment_intents.cancel_async.side_effect = StripeError(
            "already cancelled"
        )
        mock_stripe_client.v1.payment_intents.retrieve_async.return_value.status = "canceled"

        await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)

        assert (
            mock_payment_repository.update_by_id.await_args.kwargs["data"]["status"]
            == PaymentStatus.CANCELLED
        )
        mock_stripe_client.v1.refunds.create_async.assert_not_awaited()


    async def test_authorized_payment_is_voided_not_refunded(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.AUTHORIZED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()

        await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)

        mock_stripe_client.v1.payment_intents.cancel_async.assert_awaited_once_with(
            mock_payment_orm.stripe_payment_intent_id
        )
        mock_stripe_client.v1.refunds.create_async.assert_not_awaited()
        assert (
            mock_payment_repository.update_by_id.await_args.kwargs["data"]["status"]
            == PaymentStatus.CANCELLED
        )
        assert (
            mock_outbox_event_service.add_outbox_event.await_args.kwargs["event_type"]
            == "payment.cancelled"
        )


# ---------------------------------------------------------------------------
# authorization and capture
# ---------------------------------------------------------------------------

class TestAuthorization:
    async def test_new_intents_are_authorize_only(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = None
        mock_payment_repository.create.return_value = mock_payment_orm

        await payment_service_unit.create_payment_intent(
            order_id=mock_payment_orm.order_id,
            user_id=mock_payment_orm.user_id,
            user_email=mock_payment_orm.user_email,
            amount=mock_payment_orm.amount,
            currency=mock_payment_orm.currency,
        )

        params = mock_stripe_client.v1.payment_intents.create_async.await_args.args[0]
        assert params["capture_method"] == "manual"

    async def test_authorized_payment_cannot_open_a_second_intent(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.AUTHORIZED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm

        with pytest.raises(PaymentAlreadyFinalizedError):
            await payment_service_unit.create_payment_intent(
                order_id=mock_payment_orm.order_id,
                user_id=mock_payment_orm.user_id,
                user_email=mock_payment_orm.user_email,
                amount=mock_payment_orm.amount,
                currency=mock_payment_orm.currency,
            )

    async def test_capturable_webhook_authorizes_with_stripes_amount(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()

        await payment_service_unit.handle_payment_intent_amount_capturable_updated({
            "object": {
                "id": mock_payment_orm.stripe_payment_intent_id,
                "amount_capturable": 4321,
                "currency": "cad",
            }
        })

        assert (
            mock_payment_repository.update_by_id.await_args.kwargs["data"]["status"]
            == PaymentStatus.AUTHORIZED
        )
        call = mock_outbox_event_service.add_outbox_event.await_args.kwargs
        assert call["event_type"] == "payment.authorized"
        assert call["payload"].amount == 4321
        assert call["payload"].currency == "cad"

    async def test_replayed_capturable_webhook_changes_nothing(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()

        await payment_service_unit.handle_payment_intent_amount_capturable_updated({
            "object": {"id": mock_payment_orm.stripe_payment_intent_id}
        })

        mock_payment_repository.update_by_id.assert_not_awaited()
        mock_outbox_event_service.add_outbox_event.assert_not_awaited()


class TestCapturePayment:
    async def test_captures_authorized_payment_once_per_order(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.AUTHORIZED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()

        await payment_service_unit.capture_payment(mock_payment_orm.order_id)

        capture = mock_stripe_client.v1.payment_intents.capture_async.await_args
        assert capture.args[0] == mock_payment_orm.stripe_payment_intent_id
        assert capture.kwargs["options"]["idempotency_key"] == (
            f"payment_intent:capture:{mock_payment_orm.order_id}"
        )
        assert (
            mock_payment_repository.update_by_id.await_args.kwargs["data"]["status"]
            == PaymentStatus.SUCCEEDED
        )
        assert (
            mock_outbox_event_service.add_outbox_event.await_args.kwargs["event_type"]
            == "payment.succeeded"
        )

    async def test_capture_charges_less_after_a_pre_capture_refund(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.AUTHORIZED
        mock_payment_orm.capture_reduction_cents = 2_000
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()

        await payment_service_unit.capture_payment(mock_payment_orm.order_id)

        capture = mock_stripe_client.v1.payment_intents.capture_async.await_args
        assert capture.args[1] == {"amount_to_capture": mock_payment_orm.amount - 2_000}

    async def test_already_captured_payment_is_left_alone(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm

        await payment_service_unit.capture_payment(mock_payment_orm.order_id)

        mock_stripe_client.v1.payment_intents.capture_async.assert_not_awaited()

    async def test_expired_authorization_is_recorded_as_cancelled(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        from stripe import StripeError

        mock_payment_orm.status = PaymentStatus.AUTHORIZED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_outbox_event_service.add_outbox_event = AsyncMock()
        mock_stripe_client.v1.payment_intents.capture_async.side_effect = StripeError("expired")
        mock_stripe_client.v1.payment_intents.retrieve_async.return_value.status = "canceled"

        await payment_service_unit.capture_payment(mock_payment_orm.order_id)

        assert (
            mock_payment_repository.update_by_id.await_args.kwargs["data"]["status"]
            == PaymentStatus.CANCELLED
        )
        assert (
            mock_outbox_event_service.add_outbox_event.await_args.kwargs["event_type"]
            == "payment.cancelled"
        )

    async def test_uncertain_capture_failure_is_retried(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
        mock_stripe_client: MagicMock,
    ) -> None:
        from stripe import StripeError

        mock_payment_orm.status = PaymentStatus.AUTHORIZED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_stripe_client.v1.payment_intents.capture_async.side_effect = StripeError("timeout")
        mock_stripe_client.v1.payment_intents.retrieve_async.return_value.status = "requires_capture"

        with pytest.raises(PaymentCaptureError):
            await payment_service_unit.capture_payment(mock_payment_orm.order_id)
        mock_payment_repository.update_by_id.assert_not_awaited()


# ---------------------------------------------------------------------------
# handle_payment_intent_cancelled
# ---------------------------------------------------------------------------

class TestHandlePaymentIntentCancelled:
    async def test_updates_status_to_cancelled(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()

        await payment_service_unit.handle_payment_intent_cancelled({
            "object": {
                "id": mock_payment_orm.stripe_payment_intent_id,
                "metadata": {},
                "cancellation_reason": "abandoned",
            }
        })

        update_call = mock_payment_repository.update_by_id.call_args
        assert update_call[1]["data"]["status"] == PaymentStatus.CANCELLED

    async def test_raises_when_payment_not_found(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = None

        with pytest.raises(PaymentNotFoundError):
            await payment_service_unit.handle_payment_intent_cancelled({
                "object": {"id": "pi_unknown", "metadata": {}}
            })


# ---------------------------------------------------------------------------
# handle_charge_refund_updated
# ---------------------------------------------------------------------------

class TestHandleChargeRefundUpdated:
    async def test_updates_to_refunded_when_refund_succeeded(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.SUCCEEDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()

        await payment_service_unit.handle_charge_refund_updated({
            "object": {
                "status": "succeeded",
                "payment_intent": mock_payment_orm.stripe_payment_intent_id,
                "amount": mock_payment_orm.amount,
            }
        })

        update_call = mock_payment_repository.update_by_id.call_args
        assert update_call[1]["data"]["status"] == PaymentStatus.REFUNDED

    async def test_skips_non_succeeded_refund_status(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        await payment_service_unit.handle_charge_refund_updated({
            "object": {"status": "pending", "payment_intent": "pi_xxx", "amount": 999}
        })
        mock_payment_repository.get_by_field.assert_not_awaited()

    async def test_skips_already_refunded_payment(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_orm.status = PaymentStatus.REFUNDED
        mock_payment_repository.get_by_field.return_value = mock_payment_orm

        await payment_service_unit.handle_charge_refund_updated({
            "object": {
                "status": "succeeded",
                "payment_intent": mock_payment_orm.stripe_payment_intent_id,
                "amount": mock_payment_orm.amount,
            }
        })
        mock_payment_repository.update_by_id.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_payment_by_id
# ---------------------------------------------------------------------------

class TestGetPaymentById:
    async def test_returns_payment(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_id.return_value = mock_payment_orm

        result = await payment_service_unit.get_payment_by_id(mock_payment_orm.id)
        assert result == mock_payment_orm

    async def test_raises_when_not_found(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_id.return_value = None

        with pytest.raises(PaymentNotFoundError):
            await payment_service_unit.get_payment_by_id(uuid4())


# ---------------------------------------------------------------------------
# get_payments
# ---------------------------------------------------------------------------

class TestGetPayments:
    async def test_returns_list_of_payments(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_all.return_value = [mock_payment_orm]

        result = await payment_service_unit.get_payments()
        assert len(result) == 1
        assert result[0].id == mock_payment_orm.id
        assert result[0].stripe_payment_intent_id == mock_payment_orm.stripe_payment_intent_id
        assert result[0] is not mock_payment_orm

    async def test_returns_empty_list_when_no_payments(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_all.return_value = []

        assert await payment_service_unit.get_payments() == []


class _FakeSessionManager:
    def __init__(self) -> None:
        self.active = False

    @asynccontextmanager
    async def transaction(self):
        assert not self.active
        self.active = True
        try:
            yield object()
        finally:
            self.active = False


class _FakeOutboxRepository:
    events: list[SimpleNamespace] = []
    updates: list[tuple[object, dict]] = []

    def __init__(self, session, model) -> None:
        pass

    async def get_pending_with_lock(self, limit: int = 1):
        if not self.events:
            return []
        return [self.events.pop(0)]

    async def update_by_id(self, item_id, data):
        self.updates.append((item_id, data))


class TestOutboxRelayTransactionBoundaries:
    async def test_publish_happens_without_an_open_database_transaction(
        self, monkeypatch
    ) -> None:
        manager = _FakeSessionManager()
        event = SimpleNamespace(
            id=uuid4(), event_type="order.created", payload={"value": 1}, attempts=0
        )
        _FakeOutboxRepository.events = [event]
        _FakeOutboxRepository.updates = []
        monkeypatch.setattr(relay_module, "OutboxRepository", _FakeOutboxRepository)

        async def publish(event_type, payload) -> None:
            assert manager.active is False

        relay = OutboxRelay(
            session_manager=manager,
            event_router=publish,
            logger=MagicMock(),
            poll_interval=1,
            outbox_model=object,
            batch_size=1,
        )

        assert await relay.relay_once() == 1
        assert _FakeOutboxRepository.updates[-1][1]["processed"] is True

    async def test_publish_timeout_releases_claim_for_bounded_retry(
        self, monkeypatch
    ) -> None:
        manager = _FakeSessionManager()
        event = SimpleNamespace(
            id=uuid4(), event_type="order.created", payload={}, attempts=0
        )
        _FakeOutboxRepository.events = [event]
        _FakeOutboxRepository.updates = []
        monkeypatch.setattr(relay_module, "OutboxRepository", _FakeOutboxRepository)

        async def never_finishes(*args) -> None:
            await asyncio.Event().wait()

        relay = OutboxRelay(
            session_manager=manager,
            event_router=never_finishes,
            logger=MagicMock(),
            poll_interval=1,
            outbox_model=object,
            batch_size=1,
            publish_timeout_seconds=0.01,
        )

        assert await relay.relay_once() == 0
        failure = _FakeOutboxRepository.updates[-1][1]
        assert failure["attempts"] == 1
        assert failure["next_retry_at"] is not None
