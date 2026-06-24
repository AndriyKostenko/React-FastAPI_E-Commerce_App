"""Unit tests for wishlist HTTP endpoints using mocked WishlistService."""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.schemas.wishlist_schemas import WishlistSchema
from shared.shared_instances import test_settings


class TestGetMyWishlist:
    async def test_get_my_wishlist_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_wishlist_service: MagicMock
    ) -> None:
        response = await client_for_unit_testing.get(f"{test_settings.API}/wishlists/me")

        assert response.status_code == 200
        mock_route_wishlist_service.get_or_create_wishlist.assert_awaited_once_with(
            user_id=test_settings.TEST_USER_ID
        )


class TestAddItemToWishlist:
    async def test_add_item_to_wishlist_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_wishlist_service: MagicMock
    ) -> None:
        payload = {"product_id": str(test_settings.TEST_PRODUCT_ID)}

        response = await client_for_unit_testing.post(
            f"{test_settings.API}/wishlists/me/items", json=payload
        )

        assert response.status_code == 200
        mock_route_wishlist_service.add_item_to_wishlist.assert_awaited_once()
        call_kwargs = mock_route_wishlist_service.add_item_to_wishlist.call_args.kwargs
        assert call_kwargs["user_id"] == test_settings.TEST_USER_ID
        assert call_kwargs["item_data"].product_id == test_settings.TEST_PRODUCT_ID

    async def test_add_item_to_wishlist_invalid_payload_returns_422(
        self, client_for_unit_testing: AsyncClient
    ) -> None:
        response = await client_for_unit_testing.post(
            f"{test_settings.API}/wishlists/me/items",
            json={"product_id": "not-a-uuid"},
        )

        assert response.status_code == 422


class TestRemoveItemFromWishlist:
    async def test_remove_item_from_wishlist_returns_200(
        self, client_for_unit_testing: AsyncClient, mock_route_wishlist_service: MagicMock
    ) -> None:
        response = await client_for_unit_testing.delete(
            f"{test_settings.API}/wishlists/me/items/{test_settings.TEST_WISHLIST_ITEM_ID}"
        )

        assert response.status_code == 200
        mock_route_wishlist_service.remove_item_from_wishlist.assert_awaited_once_with(
            user_id=test_settings.TEST_USER_ID,
            item_id=test_settings.TEST_WISHLIST_ITEM_ID,
        )
