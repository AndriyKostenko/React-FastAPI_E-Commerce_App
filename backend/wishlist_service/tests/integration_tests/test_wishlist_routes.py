"""Integration tests for wishlist endpoints using a real PostgreSQL test database."""
from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.shared_instances import test_settings


def _add_item_payload(product_id=None) -> dict:
    return {
        "product_id": str(product_id or test_settings.TEST_PRODUCT_ID),
    }


class TestGetMyWishlistIntegration:
    async def test_get_my_wishlist_creates_wishlist_when_missing(
        self, integration_client: AsyncClient
    ) -> None:
        response = await integration_client.get(f"{test_settings.API}/wishlists/me")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(test_settings.TEST_USER_ID)
        assert data["items"] == []


class TestAddItemToWishlistIntegration:
    async def test_add_item_to_wishlist_returns_200(
        self, integration_client: AsyncClient
    ) -> None:
        response = await integration_client.post(
            f"{test_settings.API}/wishlists/me/items", json=_add_item_payload()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(test_settings.TEST_USER_ID)
        assert len(data["items"]) == 1

    async def test_add_same_product_returns_existing_item(
        self, integration_client: AsyncClient
    ) -> None:
        await integration_client.post(
            f"{test_settings.API}/wishlists/me/items", json=_add_item_payload()
        )
        response = await integration_client.post(
            f"{test_settings.API}/wishlists/me/items", json=_add_item_payload()
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1


class TestRemoveItemFromWishlistIntegration:
    async def test_remove_item_from_wishlist(
        self, integration_client: AsyncClient
    ) -> None:
        add_response = await integration_client.post(
            f"{test_settings.API}/wishlists/me/items", json=_add_item_payload()
        )
        item_id = add_response.json()["items"][0]["id"]

        response = await integration_client.delete(
            f"{test_settings.API}/wishlists/me/items/{item_id}"
        )

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_remove_nonexistent_item_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        await integration_client.post(
            f"{test_settings.API}/wishlists/me/items", json=_add_item_payload()
        )

        response = await integration_client.delete(
            f"{test_settings.API}/wishlists/me/items/{uuid4()}"
        )

        assert response.status_code == 404
