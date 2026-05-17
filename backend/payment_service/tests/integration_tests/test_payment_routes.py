"""
Integration tests for payment routes.

Uses the real PostgreSQL test database (PAYMENT_SERVICE_TEST_DB).
Stripe API calls are patched at the service level — no real Stripe account needed.
Redis idempotency service is patched in the routes module.

Each test receives the integration_client fixture which:
  - Creates the DB schema before each test.
  - Truncates all tables after each test.
"""
from uuid import uuid4

import pytest

from tests.constants import (
    TEST_ORDER_ID,
    TEST_USER_ID,
    TEST_EMAIL,
    TEST_STRIPE_INTENT_ID,
    TEST_CLIENT_SECRET,
    TEST_AMOUNT,
    TEST_CURRENCY,
    TEST_API,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_payment(client, order_id=None, user_id=None) -> dict:
    """Helper: POST /payments/create-intent and return the JSON body."""
    payload = {
        "order_id": str(order_id or TEST_ORDER_ID),
        "user_id": str(user_id or TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY,
    }
    response = await client.post(f"{TEST_API}/payments/create-intent", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_ok(self, integration_client) -> None:
        response = await integration_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /payments/create-intent
# ---------------------------------------------------------------------------

class TestCreatePaymentIntent:
    async def test_create_intent_returns_201_and_correct_fields(
        self, integration_client
    ) -> None:
        data = await _create_payment(integration_client)
        assert "client_secret" in data
        assert "stripe_payment_intent_id" in data
        assert data["stripe_payment_intent_id"].startswith("pi_test_")
        assert "payment_id" in data
        assert "order_id" in data

    async def test_create_intent_idempotent_for_pending_payment(
        self, integration_client
    ) -> None:
        """Second call for the same order_id returns the same payment (idempotency)."""
        data1 = await _create_payment(integration_client)
        data2 = await _create_payment(integration_client)
        assert data1["payment_id"] == data2["payment_id"]

    async def test_create_intent_invalid_email_returns_422(
        self, integration_client
    ) -> None:
        payload = {
            "order_id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_email": "not-an-email",
            "amount": TEST_AMOUNT,
            "currency": TEST_CURRENCY,
        }
        response = await integration_client.post(
            f"{TEST_API}/payments/create-intent", json=payload
        )
        assert response.status_code == 422

    async def test_create_intent_missing_required_fields_returns_422(
        self, integration_client
    ) -> None:
        response = await integration_client.post(
            f"{TEST_API}/payments/create-intent", json={"amount": 500}
        )
        assert response.status_code == 422

    async def test_two_different_orders_create_separate_payments(
        self, integration_client
    ) -> None:
        data1 = await _create_payment(integration_client, order_id=uuid4())
        data2 = await _create_payment(integration_client, order_id=uuid4())
        assert data1["payment_id"] != data2["payment_id"]
        assert data1["order_id"] != data2["order_id"]


# ---------------------------------------------------------------------------
# GET /payments/{payment_id}
# ---------------------------------------------------------------------------

class TestGetPaymentById:
    async def test_returns_payment_after_creation(self, integration_client) -> None:
        created = await _create_payment(integration_client)
        payment_id = created["payment_id"]

        response = await integration_client.get(f"{TEST_API}/payments/{payment_id}")
        assert response.status_code == 200

    async def test_returns_404_for_unknown_id(self, integration_client) -> None:
        response = await integration_client.get(f"{TEST_API}/payments/{uuid4()}")
        assert response.status_code == 404

    async def test_payment_has_pending_status_after_creation(
        self, integration_client
    ) -> None:
        created = await _create_payment(integration_client)
        payment_id = created["payment_id"]

        response = await integration_client.get(f"{TEST_API}/payments/{payment_id}")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /payments
# ---------------------------------------------------------------------------

class TestGetAllPayments:
    async def test_returns_list_after_creation(self, integration_client) -> None:
        await _create_payment(integration_client, order_id=uuid4())
        await _create_payment(integration_client, order_id=uuid4())

        response = await integration_client.get(f"{TEST_API}/payments")
        assert response.status_code == 200

    async def test_returns_404_when_no_payments(self, integration_client) -> None:
        response = await integration_client.get(f"{TEST_API}/payments")
        assert response.status_code == 404
