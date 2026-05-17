"""Integration tests for order endpoints using a real PostgreSQL test database."""
from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from tests.constants import (
    TEST_USER_ID, TEST_EMAIL, TEST_AMOUNT, TEST_CURRENCY,
    TEST_PAYMENT_INTENT_ID, TEST_PRODUCT_ID, TEST_API,
)


def _order_payload(**overrides) -> dict:
    base = {
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY,
        "payment_intent_id": str(uuid4()),  # unique per test
        "products": [
            {
                "id": str(TEST_PRODUCT_ID),
                "name": "Test Widget",
                "price": "49.99",
                "quantity": 2,
            }
        ],
        "address": {
            "street": "123 Integration Ave",
            "city": "Test City",
            "province": "TC",
            "postal_code": "T2T 2T2",
        },
    }
    base.update(overrides)
    return base


class TestCreateOrderIntegration:
    async def test_create_order_returns_201(self, integration_client: AsyncClient):
        response = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        assert response.status_code == 201

    async def test_create_order_response_has_expected_fields(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        data = response.json()
        assert "id" in data
        assert data["user_email"] == TEST_EMAIL
        assert data["status"] == OrderStatus.PENDING
        assert data["delivery_status"] == OrderDeliveryStatus.PENDING

    async def test_create_order_duplicate_payment_intent_returns_409(
        self, integration_client: AsyncClient
    ):
        fixed_intent = str(uuid4())
        payload = _order_payload(payment_intent_id=fixed_intent)

        await integration_client.post(f"{TEST_API}/orders", json=payload)
        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 409


class TestGetOrdersIntegration:
    async def test_get_orders_returns_200(self, integration_client: AsyncClient):
        await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        response = await integration_client.get(f"{TEST_API}/orders")
        assert response.status_code == 200

    async def test_get_orders_returns_list(self, integration_client: AsyncClient):
        await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        response = await integration_client.get(f"{TEST_API}/orders")
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    async def test_get_orders_empty_returns_404(self, integration_client: AsyncClient):
        # No orders created in this test — table was truncated before this fixture
        response = await integration_client.get(f"{TEST_API}/orders")
        assert response.status_code == 404


class TestGetOrderByIdIntegration:
    async def test_get_order_by_id_returns_200(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert response.status_code == 200
        assert response.json()["id"] == order_id

    async def test_get_order_by_id_not_found_returns_404(
        self, integration_client: AsyncClient
    ):
        fake_id = str(uuid4())
        response = await integration_client.get(f"{TEST_API}/orders/{fake_id}")
        assert response.status_code == 404


class TestGetOrdersByUserIdIntegration:
    async def test_get_orders_by_user_id_returns_200(
        self, integration_client: AsyncClient
    ):
        await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        response = await integration_client.get(
            f"{TEST_API}/orders/user/{TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(o["user_id"] == str(TEST_USER_ID) for o in data)


class TestUpdateOrderIntegration:
    async def test_update_order_delivery_status(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}",
            json={"delivery_status": OrderDeliveryStatus.CONFIRMED, "amount": TEST_AMOUNT},
        )
        assert response.status_code == 200
        assert response.json()["delivery_status"] == OrderDeliveryStatus.CONFIRMED

    async def test_update_order_status_to_confirmed(
        self, integration_client: AsyncClient
    ):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}",
            json={"status": OrderStatus.CONFIRMED, "amount": TEST_AMOUNT},
        )
        assert response.status_code == 200
        assert response.json()["status"] == OrderStatus.CONFIRMED


class TestCancelOrderIntegration:
    async def test_cancel_pending_order_returns_200(
        self, integration_client: AsyncClient
    ):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "Integration test cancellation"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == OrderStatus.CANCELLED

    async def test_cancel_already_cancelled_order_returns_409(
        self, integration_client: AsyncClient
    ):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "First cancellation"},
        )
        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "Second cancellation"},
        )
        assert response.status_code == 409


class TestDeleteOrderIntegration:
    async def test_delete_order_returns_204(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.delete(f"{TEST_API}/orders/{order_id}")
        assert response.status_code == 204

    async def test_deleted_order_is_not_found(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        await integration_client.delete(f"{TEST_API}/orders/{order_id}")
        response = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert response.status_code == 404
