"""Unit tests for cart HTTP endpoints using mocked CartService."""
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.schemas.cart_schemas import CartSchema, CartSummary
from shared.shared_instances import test_settings


# ---------------------------------------------------------------------------
# GET /users/{user_id}/cart
# ---------------------------------------------------------------------------

class TestGetCart:
    async def test_get_cart_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_cart_service: MagicMock
    ) -> None:
        response = await client_for_unit_testing.get(f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart")

        assert response.status_code == 200
        mock_route_cart_service.get_or_create_cart.assert_awaited_once_with(user_id=test_settings.TEST_USER_ID)


# ---------------------------------------------------------------------------
# GET /users/{user_id}/cart/summary
# ---------------------------------------------------------------------------

class TestGetCartSummary:
    async def test_get_cart_summary_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_cart_service: MagicMock
    ) -> None:
        response = await client_for_unit_testing.get(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart/summary"
        )

        assert response.status_code == 200
        mock_route_cart_service.get_cart_summary.assert_awaited_once_with(user_id=test_settings.TEST_USER_ID)


# ---------------------------------------------------------------------------
# POST /users/{user_id}/cart/items
# ---------------------------------------------------------------------------

class TestAddItemToCart:
    async def test_add_item_to_cart_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_cart_service: MagicMock
    ) -> None:
        payload = {
            "product_id": str(test_settings.TEST_PRODUCT_ID),
            "quantity": 2,
            "price_snapshot": "9.99",
        }

        response = await client_for_unit_testing.post(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart/items", json=payload
        )

        assert response.status_code == 200
        mock_route_cart_service.add_item_to_cart.assert_awaited_once()
        call_kwargs = mock_route_cart_service.add_item_to_cart.call_args.kwargs
        assert call_kwargs["user_id"] == test_settings.TEST_USER_ID
        assert call_kwargs["item_data"].product_id == test_settings.TEST_PRODUCT_ID
        assert call_kwargs["item_data"].quantity == 2
        assert call_kwargs["item_data"].price_snapshot == Decimal("9.99")

    async def test_add_item_to_cart_invalid_payload_returns_422(
        self, client_for_unit_testing: AsyncClient
    ) -> None:
        response = await client_for_unit_testing.post(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart/items",
            json={"product_id": "not-a-uuid", "quantity": 2, "price_snapshot": "9.99"},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /users/{user_id}/cart/items/{item_id}
# ---------------------------------------------------------------------------

class TestUpdateCartItem:
    async def test_update_cart_item_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_cart_service: MagicMock
    ) -> None:
        payload = {"quantity": 5}

        response = await client_for_unit_testing.put(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart/items/{test_settings.TEST_CART_ITEM_ID}",
            json=payload,
        )

        assert response.status_code == 200
        mock_route_cart_service.update_item_quantity.assert_awaited_once()
        call_kwargs = mock_route_cart_service.update_item_quantity.call_args.kwargs
        assert call_kwargs["user_id"] == test_settings.TEST_USER_ID
        assert call_kwargs["item_id"] == test_settings.TEST_CART_ITEM_ID
        assert call_kwargs["item_data"].quantity == 5

    async def test_update_cart_item_invalid_quantity_returns_422(
        self, client_for_unit_testing: AsyncClient
    ) -> None:
        response = await client_for_unit_testing.put(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart/items/{test_settings.TEST_CART_ITEM_ID}",
            json={"quantity": 0},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/cart/items/{item_id}
# ---------------------------------------------------------------------------

class TestRemoveCartItem:
    async def test_remove_cart_item_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_cart_service: MagicMock
    ) -> None:
        response = await client_for_unit_testing.delete(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart/items/{test_settings.TEST_CART_ITEM_ID}"
        )

        assert response.status_code == 200
        mock_route_cart_service.remove_item_from_cart.assert_awaited_once_with(
            user_id=test_settings.TEST_USER_ID, item_id=test_settings.TEST_CART_ITEM_ID
        )


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/cart
# ---------------------------------------------------------------------------

class TestClearCart:
    async def test_clear_cart_returns_204(
        self, client_for_unit_testing: AsyncClient, mock_route_cart_service: MagicMock
    ) -> None:
        response = await client_for_unit_testing.delete(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}/cart"
        )

        assert response.status_code == 204
        mock_route_cart_service.clear_cart.assert_awaited_once_with(user_id=test_settings.TEST_USER_ID)
