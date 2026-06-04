"""Unit tests for order, notification, and payment proxy routes."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse
from httpx import Response as HttpxResponse
from httpx import AsyncClient

from gateway.apigateway import ApiGateway
from tests.constants import (
    TEST_ORDER_ID, TEST_NOTIFICATION_ID, TEST_PAYMENT_ID,
    TEST_USER_ID, TEST_API,
)


# ---------------------------------------------------------------------------
# Order routes
# ---------------------------------------------------------------------------

class TestOrderRoutes:
    async def test_create_order_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(f"{TEST_API}/orders", json={"items": []})
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_get_all_orders_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/orders")
        mock_forward.assert_awaited_once()

    async def test_get_orders_by_user_own_id_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/orders/user/{TEST_USER_ID}")
        mock_forward.assert_awaited_once()

    async def test_get_orders_by_user_other_id_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        other_id = uuid4()
        response = await client.get(f"{TEST_API}/orders/user/{other_id}")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_get_order_by_id_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/orders/{TEST_ORDER_ID}")
        mock_forward.assert_awaited_once()

    async def test_cancel_order_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.patch(f"{TEST_API}/orders/{TEST_ORDER_ID}/cancel")
        mock_forward.assert_awaited_once()

    async def test_update_order_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.patch(f"{TEST_API}/orders/{TEST_ORDER_ID}", json={"status": "confirmed"})
        mock_forward.assert_awaited_once()

    async def test_delete_order_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.delete(f"{TEST_API}/orders/{TEST_ORDER_ID}")
        mock_forward.assert_awaited_once()

    async def test_delete_order_as_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.delete(f"{TEST_API}/orders/{TEST_ORDER_ID}")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_create_order_injects_user_id_in_body(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        """create_order route enriches the body with user_id from the JWT payload."""
        await client.post(f"{TEST_API}/orders", json={"items": [{"product_id": "abc", "quantity": 1}]})
        call_kwargs = mock_forward.call_args.kwargs
        assert call_kwargs["override_body"]["user_id"] == str(TEST_USER_ID)


# ---------------------------------------------------------------------------
# Notification routes
# ---------------------------------------------------------------------------

class TestNotificationRoutes:
    async def test_get_user_notifications_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/notifications/users/{TEST_USER_ID}")
        mock_forward.assert_awaited_once()

    async def test_get_unread_count_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/notifications/users/{TEST_USER_ID}/unread-count")
        mock_forward.assert_awaited_once()

    async def test_mark_notification_as_read_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.patch(f"{TEST_API}/notifications/{TEST_NOTIFICATION_ID}/read")
        mock_forward.assert_awaited_once()

    async def test_mark_all_as_read_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.patch(f"{TEST_API}/notifications/users/{TEST_USER_ID}/read-all")
        mock_forward.assert_awaited_once()

    async def test_delete_notification_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.delete(f"{TEST_API}/notifications/{TEST_NOTIFICATION_ID}")
        mock_forward.assert_awaited_once()


# ---------------------------------------------------------------------------
# Payment routes
# ---------------------------------------------------------------------------

class TestPaymentRoutes:
    async def test_create_payment_intent_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(
            f"{TEST_API}/payments/create-intent",
            json={"order_id": str(TEST_ORDER_ID), "amount": 99.99, "currency": "USD"},
        )
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_create_payment_intent_injects_user_id(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        await client.post(
            f"{TEST_API}/payments/create-intent",
            json={"order_id": str(TEST_ORDER_ID), "amount": 50.0, "currency": "USD"},
        )
        call_kwargs = mock_forward.call_args.kwargs
        assert call_kwargs["override_body"]["user_id"] == str(TEST_USER_ID)

    async def test_stripe_webhook_public_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(f"{TEST_API}/payments/webhook", content=b"stripe payload")
        mock_forward.assert_awaited_once()

    async def test_get_payment_by_id_authenticated_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        """GET /payments/{id} calls require_user_or_admin with no target — only admin can access."""
        response = await admin_client.get(f"{TEST_API}/payments/{TEST_PAYMENT_ID}")
        mock_forward.assert_awaited_once()

    async def test_get_payment_by_id_as_regular_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        """Regular user without target_user_id match is denied."""
        response = await client.get(f"{TEST_API}/payments/{TEST_PAYMENT_ID}")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_get_payments_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.get(f"{TEST_API}/payments")
        mock_forward.assert_awaited_once()

    async def test_get_payments_as_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/payments")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    async def test_health_returns_200_with_status_ok(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "api-gateway"
        mock_forward.assert_not_awaited()


class TestMediaProxy:
    async def test_media_proxy_returns_binary_from_product_service(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(
            return_value=HttpxResponse(
                status_code=200,
                content=b"image-bytes",
                headers={"content-type": "image/png"},
            )
        )

        with patch.object(ApiGateway, "_http_client", mock_http_client):
            response = await client.get("/media/generated/test.png")

        assert response.status_code == 200
        assert response.content == b"image-bytes"
        assert response.headers["content-type"].startswith("image/png")
        mock_forward.assert_not_awaited()
