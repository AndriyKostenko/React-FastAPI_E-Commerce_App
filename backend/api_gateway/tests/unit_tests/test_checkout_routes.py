"""Unit tests for the checkout orchestration routes."""
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from httpx import Response as HttpxResponse

from tests.constants import TEST_API, TEST_ORDER_ID, TEST_USER_EMAIL, TEST_USER_ID


ORDER = {
    "id": str(TEST_ORDER_ID),
    "user_id": str(TEST_USER_ID),
    "status": "pending",
    "currency": "cad",
    "amount": 73.22,
    "amount_cents": 7322,
    "subtotal_amount": "55.53",
    "shipping_amount": "17.69",
    "tax_amount": "0.00",
    "shipping_logistic_name": "CJPacket Ordinary",
}
INTENT = {
    "client_secret": "pi_123_secret_abc",
    "stripe_payment_intent_id": "pi_123",
    "payment_id": str(uuid4()),
    "order_id": str(TEST_ORDER_ID),
    "amount": 7322,
    "currency": "cad",
}
CHECKOUT_BODY = {
    "products": [{"id": str(uuid4()), "variant_id": str(uuid4()), "quantity": 1}],
    "address": {"street": "1 Main St", "city": "Calgary", "province": "AB", "postal_code": "T1T 1T1"},
    "shipping_logistic_name": "CJPacket Ordinary",
}


class ServiceStub:
    """Answers service-to-service calls by (method, path) and records them."""

    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], HttpxResponse] = {
            ("POST", "/orders/quote"): HttpxResponse(200, json={"amount_cents": 7322}),
            ("POST", "/orders"): HttpxResponse(201, json=ORDER),
            ("GET", f"/orders/{TEST_ORDER_ID}"): HttpxResponse(200, json=ORDER),
            ("POST", "/payments/create-intent"): HttpxResponse(201, json=INTENT),
            ("PATCH", f"/orders/{TEST_ORDER_ID}/cancel"): HttpxResponse(200, json=ORDER),
        }
        self.calls: list[dict[str, Any]] = []

    async def request(self, _request, service, path, *, method="GET", json=None):
        self.calls.append({"service": service, "path": path, "method": method, "json": json})
        return self.responses[(method, path)]

    def call(self, method: str, path: str) -> dict[str, Any] | None:
        return next(
            (c for c in self.calls if c["method"] == method and c["path"] == path),
            None,
        )


@pytest.fixture
def service_stub() -> ServiceStub:
    return ServiceStub()


@pytest.fixture
def mock_service_request(service_stub: ServiceStub) -> AsyncMock:
    return AsyncMock(side_effect=service_stub.request)


class TestCheckoutQuote:
    async def test_forwards_only_cart_address_and_shipping(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        response = await client.post(
            f"{TEST_API}/checkout/quote",
            json={**CHECKOUT_BODY, "amount": 1, "user_id": str(uuid4())},
        )

        assert response.status_code == 200
        sent = service_stub.call("POST", "/orders/quote")["json"]
        assert set(sent) == {"products", "address", "shipping_logistic_name"}


class TestStartCheckout:
    async def test_creates_order_then_intent_for_the_order_amount(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        response = await client.post(
            f"{TEST_API}/checkout",
            json={**CHECKOUT_BODY, "amount": 1, "user_id": str(uuid4())},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["client_secret"] == "pi_123_secret_abc"
        assert body["amount_cents"] == 7322

        order_call = service_stub.call("POST", "/orders")["json"]
        assert order_call["user_id"] == str(TEST_USER_ID)
        assert order_call["user_email"] == TEST_USER_EMAIL
        assert "amount" not in order_call

        intent_call = service_stub.call("POST", "/payments/create-intent")["json"]
        assert intent_call == {
            "order_id": str(TEST_ORDER_ID),
            "user_id": str(TEST_USER_ID),
            "user_email": TEST_USER_EMAIL,
            "amount": 7322,
            "currency": "cad",
        }

    async def test_resume_reuses_the_callers_pending_order(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        response = await client.post(
            f"{TEST_API}/checkout", json={"order_id": str(TEST_ORDER_ID)}
        )

        assert response.status_code == 200
        assert service_stub.call("POST", "/orders") is None
        assert service_stub.call("POST", "/payments/create-intent") is not None

    async def test_resume_hides_another_users_order(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        service_stub.responses[("GET", f"/orders/{TEST_ORDER_ID}")] = HttpxResponse(
            200, json={**ORDER, "user_id": str(uuid4())}
        )

        response = await client.post(
            f"{TEST_API}/checkout", json={"order_id": str(TEST_ORDER_ID)}
        )

        assert response.status_code == 404
        assert service_stub.call("POST", "/payments/create-intent") is None

    async def test_resume_refuses_an_order_no_longer_pending(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        service_stub.responses[("GET", f"/orders/{TEST_ORDER_ID}")] = HttpxResponse(
            200, json={**ORDER, "status": "cancelled"}
        )

        response = await client.post(
            f"{TEST_API}/checkout", json={"order_id": str(TEST_ORDER_ID)}
        )

        assert response.status_code == 409
        assert response.json()["order_status"] == "cancelled"
        assert service_stub.call("POST", "/payments/create-intent") is None

    async def test_resume_of_an_already_authorized_order_says_it_was_placed(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        service_stub.responses[("POST", "/payments/create-intent")] = HttpxResponse(
            409, json={"detail": "Payment for order is already finalized"}
        )

        response = await client.post(
            f"{TEST_API}/checkout", json={"order_id": str(TEST_ORDER_ID)}
        )

        assert response.status_code == 409
        assert response.json()["order_status"] == "payment_authorized"
        assert service_stub.call("PATCH", f"/orders/{TEST_ORDER_ID}/cancel") is None

    async def test_rejects_malformed_order_id(self, client: AsyncClient, service_stub: ServiceStub):
        response = await client.post(f"{TEST_API}/checkout", json={"order_id": "nope"})

        assert response.status_code == 422
        assert service_stub.calls == []

    async def test_order_quote_error_is_returned_without_opening_payment(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        service_stub.responses[("POST", "/orders")] = HttpxResponse(
            422, json={"detail": "Shipping option 'x' is no longer available"}
        )

        response = await client.post(f"{TEST_API}/checkout", json=CHECKOUT_BODY)

        assert response.status_code == 422
        assert "no longer available" in response.json()["detail"]
        assert service_stub.call("POST", "/payments/create-intent") is None

    async def test_intent_failure_cancels_the_order_it_just_created(
        self, client: AsyncClient, service_stub: ServiceStub
    ):
        service_stub.responses[("POST", "/payments/create-intent")] = HttpxResponse(
            502, json={"detail": "Stripe unavailable"}
        )

        response = await client.post(f"{TEST_API}/checkout", json=CHECKOUT_BODY)

        assert response.status_code == 502
        cancel = service_stub.call("PATCH", f"/orders/{TEST_ORDER_ID}/cancel")
        assert cancel is not None
