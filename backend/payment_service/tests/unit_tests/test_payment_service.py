"""
Unit tests for PaymentService.

All external dependencies (repository, Stripe, outbox service) are mocked
so every test runs without a live database or Stripe account.
"""
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
)
from models.payment_models import Payment
from shared.enums.status_enums import PaymentStatus


# ---------------------------------------------------------------------------
# create_payment_intent
# ---------------------------------------------------------------------------

class TestCreatePaymentIntent:
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
        mock_stripe_client.v1.payment_intents.create.side_effect = StripeError("Network error")

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
    async def test_updates_status_to_failed_and_records_reason(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
        mock_outbox_event_service,
        mock_payment_orm: MagicMock,
    ) -> None:
        mock_payment_repository.get_by_field.return_value = mock_payment_orm
        mock_payment_repository.update_by_id.return_value = mock_payment_orm
        mock_outbox_event_service.repository.create.return_value = MagicMock()

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
        assert update_call[1]["data"]["status"] == PaymentStatus.FAILED
        assert update_call[1]["data"]["failure_reason"] == failure_msg

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

        mock_stripe_client.v1.refunds.create.assert_called_once()
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
        mock_stripe_client.v1.refunds.create.side_effect = StripeError("Refund failed")

        with pytest.raises(PaymentRefundError):
            await payment_service_unit.handle_payment_refund(mock_payment_orm.order_id)


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
        assert result[0] == mock_payment_orm

    async def test_raises_when_no_payments(
        self,
        payment_service_unit,
        mock_payment_repository: MagicMock,
    ) -> None:
        mock_payment_repository.get_all.return_value = None

        with pytest.raises(PaymentsNotFoundError):
            await payment_service_unit.get_payments()
