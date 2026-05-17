"""
Route-level unit tests for payment_service.

All services and infrastructure (DB, Stripe, Redis) are replaced with mocks.
Tests exercise the HTTP layer: request validation, status codes, and response shape.
"""
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.constants import TEST_PAYMENT_ID, TEST_ORDER_ID, TEST_USER_ID, TEST_EMAIL
from tests.constants import TEST_STRIPE_INTENT_ID, TEST_CLIENT_SECRET, TEST_AMOUNT, TEST_CURRENCY
from tests.constants import TEST_API, MOCK_PAYMENT_INTENT_RESULT
from exceptions.payment_exceptions import (
    PaymentNotFoundError,
    PaymentsNotFoundError,
    PaymentAlreadyFinalizedError,
    InvalidStripeWebhookSignature,
    PaymentDataIsNotProvided,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_ok(self, client_for_unit_testing) -> None:
        response = await client_for_unit_testing.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "payment-service"


# ---------------------------------------------------------------------------
# POST /payments/create-intent
# ---------------------------------------------------------------------------

class TestCreatePaymentIntentEndpoint:
    async def test_create_intent_returns_201(self, client_for_unit_testing) -> None:
        payload = {
            "order_id": str(TEST_ORDER_ID),
            "user_id": str(TEST_USER_ID),
            "user_email": TEST_EMAIL,
            "amount": TEST_AMOUNT,
            "currency": TEST_CURRENCY,
        }
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/create-intent", json=payload
        )
        assert response.status_code == 201
        data = response.json()
        assert "client_secret" in data
        assert "stripe_payment_intent_id" in data
        assert "payment_id" in data

    async def test_create_intent_invalid_payload_returns_422(
        self, client_for_unit_testing
    ) -> None:
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/create-intent", json={"amount": "not-an-int"}
        )
        assert response.status_code == 422

    async def test_create_intent_already_finalized_returns_409(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_route_payment_service.create_payment_intent.side_effect = (
            PaymentAlreadyFinalizedError(order_id=TEST_ORDER_ID)
        )
        payload = {
            "order_id": str(TEST_ORDER_ID),
            "user_id": str(TEST_USER_ID),
            "user_email": TEST_EMAIL,
            "amount": TEST_AMOUNT,
            "currency": TEST_CURRENCY,
        }
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/create-intent", json=payload
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /payments/webhook
# ---------------------------------------------------------------------------

class TestWebhookEndpoint:
    def _webhook_payload(self, event_type: str, intent_id: str = TEST_STRIPE_INTENT_ID) -> bytes:
        return json.dumps({
            "type": event_type,
            "id": f"evt_{uuid4().hex}",
            "data": {
                "object": {
                    "id": intent_id,
                    "metadata": {
                        "order_id": str(TEST_ORDER_ID),
                        "user_id": str(TEST_USER_ID),
                    },
                }
            },
        }).encode()

    async def test_webhook_succeeded_returns_200(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        raw = self._webhook_payload("payment_intent.succeeded")
        mock_route_payment_service.construct_webhook_event.return_value = {
            "type": "payment_intent.succeeded",
            "id": "evt_test_succeeded",
            "data": {"object": {"id": TEST_STRIPE_INTENT_ID, "metadata": {}}},
        }
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/webhook",
            content=raw,
            headers={"stripe-signature": "t=1,v1=fakesig"},
        )
        assert response.status_code == 200
        assert response.json()["received"] is True

    async def test_webhook_failed_returns_200(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_route_payment_service.construct_webhook_event.return_value = {
            "type": "payment_intent.payment_failed",
            "id": "evt_test_failed",
            "data": {"object": {"id": TEST_STRIPE_INTENT_ID, "metadata": {}, "last_payment_error": {}}},
        }
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fakesig"},
        )
        assert response.status_code == 200

    async def test_webhook_cancelled_returns_200(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_route_payment_service.construct_webhook_event.return_value = {
            "type": "payment_intent.canceled",
            "id": "evt_test_cancelled",
            "data": {"object": {"id": TEST_STRIPE_INTENT_ID, "metadata": {}}},
        }
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fakesig"},
        )
        assert response.status_code == 200

    async def test_webhook_duplicate_event_returns_200_with_idempotency_flag(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        """Duplicate events (idempotency service returns False) are acknowledged silently."""
        from unittest.mock import patch, AsyncMock
        mock_route_payment_service.construct_webhook_event.return_value = {
            "type": "payment_intent.succeeded",
            "id": "evt_duplicate",
            "data": {"object": {"id": TEST_STRIPE_INTENT_ID, "metadata": {}}},
        }
        mock_idempotency = MagicMock()
        mock_idempotency.try_claim_event = AsyncMock(return_value=False)

        with patch("routes.payment_routes.idempotency_service", mock_idempotency):
            response = await client_for_unit_testing.post(
                f"{TEST_API}/payments/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=fakesig"},
            )
        assert response.status_code == 200
        assert response.json()["idempotency"] == "duplicate"

    async def test_webhook_unknown_event_type_returns_200(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_route_payment_service.construct_webhook_event.return_value = {
            "type": "some.unknown.event",
            "id": "evt_unknown",
            "data": {"object": {}},
        }
        response = await client_for_unit_testing.post(
            f"{TEST_API}/payments/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fakesig"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /payments/{payment_id}
# ---------------------------------------------------------------------------

class TestGetPaymentByIdEndpoint:
    async def test_get_payment_returns_200(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_payment = MagicMock()
        mock_payment.id = TEST_PAYMENT_ID
        mock_payment.order_id = TEST_ORDER_ID
        mock_payment.status = "pending"
        mock_route_payment_service.get_payment_by_id.return_value = mock_payment

        response = await client_for_unit_testing.get(
            f"{TEST_API}/payments/{TEST_PAYMENT_ID}"
        )
        assert response.status_code == 200

    async def test_get_payment_not_found_returns_404(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        unknown_id = uuid4()
        mock_route_payment_service.get_payment_by_id.side_effect = (
            PaymentNotFoundError(payment_id=unknown_id)
        )
        response = await client_for_unit_testing.get(
            f"{TEST_API}/payments/{unknown_id}"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /payments
# ---------------------------------------------------------------------------

class TestGetAllPaymentsEndpoint:
    async def test_get_payments_returns_200(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_payment = MagicMock()
        mock_payment.id = TEST_PAYMENT_ID
        mock_route_payment_service.get_payments.return_value = [mock_payment]

        response = await client_for_unit_testing.get(f"{TEST_API}/payments")
        assert response.status_code == 200

    async def test_get_payments_returns_404_when_empty(
        self, client_for_unit_testing, mock_route_payment_service: MagicMock
    ) -> None:
        mock_route_payment_service.get_payments.side_effect = PaymentsNotFoundError()

        response = await client_for_unit_testing.get(f"{TEST_API}/payments")
        assert response.status_code == 404
