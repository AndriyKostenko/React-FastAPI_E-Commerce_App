"""Route-level unit tests for order endpoints (all DB/IO mocked)."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.settings import get_settings
from shared.testing.signing_keys import GatewayCallerAuth
from tests.conftest import SIGNING_KEYS

from exceptions.order_exceptions import (
    OrderNotFoundError, OrdersNotFoundError, OrderNotCancellableError
)
from tests.constants import (
    TEST_ORDER_ID, TEST_USER_ID, TEST_EMAIL, TEST_AMOUNT, TEST_CURRENCY,
    TEST_PAYMENT_INTENT_ID, TEST_ORDER_ADDRESS_ID, TEST_DATETIME, TEST_API,
    MOCK_ORDER_RESULT,
)
from shared.testing.signing_keys import ANONYMOUS


def _order_payload(**overrides) -> dict:
    base = {
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY,
        "payment_intent_id": TEST_PAYMENT_INTENT_ID,
        "products": [
            {
                "id": str(TEST_ORDER_ID),
                "name": "Widget",
                "price": "49.99",
                "quantity": 2,
            }
        ],
        "address": {
            "street": "123 Test St",
            "city": "Testville",
            "province": "TS",
            "postal_code": "T1T 1T1",
        },
    }
    base.update(overrides)
    return base


class TestCreateOrderRoute:
    async def test_create_order_returns_201(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        assert response.status_code == 201

    async def test_create_order_calls_service(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        await client_for_unit_testing.post(f"{TEST_API}/orders", json=_order_payload())
        mock_route_order_service.create_order.assert_awaited_once()

    async def test_create_order_service_error_propagates(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.create_order = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        with pytest.raises(Exception, match="Unexpected error"):
            await client_for_unit_testing.post(
                f"{TEST_API}/orders", json=_order_payload()
            )


class TestGetOrdersRoute:
    async def test_get_orders_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.get(f"{TEST_API}/orders")
        assert response.status_code == 200

    async def test_get_orders_returns_list(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.get(f"{TEST_API}/orders")
        assert isinstance(response.json(), list)

    async def test_get_orders_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.get_orders = AsyncMock(side_effect=OrdersNotFoundError())
        response = await client_for_unit_testing.get(f"{TEST_API}/orders")
        assert response.status_code == 404


class TestGetOrderByIdRoute:
    async def test_get_order_by_id_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.get(f"{TEST_API}/orders/{TEST_ORDER_ID}")
        assert response.status_code == 200

    async def test_get_order_by_id_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.get_order_by_id = AsyncMock(
            side_effect=OrderNotFoundError(TEST_ORDER_ID)
        )
        response = await client_for_unit_testing.get(f"{TEST_API}/orders/{TEST_ORDER_ID}")
        assert response.status_code == 404


class TestGetOrdersByUserIdRoute:
    async def test_get_orders_by_user_id_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/orders/user/{TEST_USER_ID}"
        )
        assert response.status_code == 200

    async def test_get_orders_by_user_id_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.get_orders_by_user_id = AsyncMock(
            side_effect=OrdersNotFoundError()
        )
        response = await client_for_unit_testing.get(
            f"{TEST_API}/orders/user/{TEST_USER_ID}"
        )
        assert response.status_code == 404


class TestUpdateOrderRoute:
    async def test_update_order_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        payload = {"delivery_status": "delivered", "amount": TEST_AMOUNT}
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/orders/{TEST_ORDER_ID}", json=payload
        )
        assert response.status_code == 200

    async def test_update_order_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.update_order = AsyncMock(
            side_effect=OrderNotFoundError(TEST_ORDER_ID)
        )
        payload = {"amount": TEST_AMOUNT}
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/orders/{TEST_ORDER_ID}", json=payload
        )
        assert response.status_code == 404


class TestCancelOrderRoute:
    async def test_cancel_order_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/orders/{TEST_ORDER_ID}/cancel",
            json={"reason": "Changed mind"},
        )
        assert response.status_code == 200

    async def test_cancel_already_cancelled_returns_409(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.cancel_order = AsyncMock(
            side_effect=OrderNotCancellableError(TEST_ORDER_ID, "cancelled")
        )
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/orders/{TEST_ORDER_ID}/cancel",
            json={"reason": "test"},
        )
        assert response.status_code == 409


class TestDeleteOrderRoute:
    async def test_delete_order_returns_204(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/orders/{TEST_ORDER_ID}"
        )
        assert response.status_code == 204

    async def test_delete_order_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_order_service: MagicMock
    ):
        mock_route_order_service.delete_order_by_id = AsyncMock(
            side_effect=OrderNotFoundError(TEST_ORDER_ID)
        )
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/orders/{TEST_ORDER_ID}"
        )
        assert response.status_code == 404


class TestAdminSchemaRoute:
    """The schema is admin-only; identity arrives as the gateway's signed assertion."""

    @staticmethod
    def _caller(role: str) -> GatewayCallerAuth:
        return SIGNING_KEYS.caller_auth(user_id=uuid4(), role=role)

    async def test_admin_gets_schema_fields(
        self, client_for_unit_testing: AsyncClient
    ):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/admin/schema/orders",
            auth=self._caller(get_settings().SECRET_ROLE),
        )
        assert response.status_code == 200
        assert response.json()["fields"]

    async def test_regular_user_is_forbidden(
        self, client_for_unit_testing: AsyncClient
    ):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/admin/schema/orders", auth=self._caller("user"),
        )
        assert response.status_code == 403

    async def test_anonymous_is_rejected(
        self, client_for_unit_testing: AsyncClient
    ):
        response = await client_for_unit_testing.get(f"{TEST_API}/admin/schema/orders", auth=ANONYMOUS)
        assert response.status_code == 401
