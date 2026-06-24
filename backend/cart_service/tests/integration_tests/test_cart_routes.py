"""Integration tests for cart endpoints using a real PostgreSQL test database."""
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.shared_instances import test_settings


def _add_item_payload(**overrides) -> dict:
    base = {
        "product_id": str(test_settings.TEST_PRODUCT_ID),
        "quantity": 2,
        "price_snapshot": str(test_settings.TEST_CART_PRICE_SNAPSHOT),
    }
    base.update(overrides)
    return base


class TestGetCartIntegration:
    async def test_get_cart_creates_cart_when_missing(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        response = await integration_client.get(f"{test_settings.API}/users/{user_id}/cart")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(user_id)
        assert data["items"] == []


class TestGetCartSummaryIntegration:
    async def test_get_cart_summary_returns_totals(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )

        response = await integration_client.get(
            f"{test_settings.API}/users/{user_id}/cart/summary"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(user_id)
        assert data["total_items"] == 2
        assert Decimal(data["total_amount"]) == Decimal("19.98")
        assert len(data["items"]) == 1


class TestAddItemToCartIntegration:
    async def test_add_item_to_cart_returns_200(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        response = await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(user_id)
        assert len(data["items"]) == 1
        assert data["items"][0]["quantity"] == 2

    async def test_add_same_product_increases_quantity(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload(quantity=2)
        )
        response = await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload(quantity=3)
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["quantity"] == 5


class TestUpdateCartItemIntegration:
    async def test_update_item_quantity(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        add_response = await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )
        item_id = add_response.json()["items"][0]["id"]

        response = await integration_client.put(
            f"{test_settings.API}/users/{user_id}/cart/items/{item_id}",
            json={"quantity": 7},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["quantity"] == 7

    async def test_update_nonexistent_item_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )

        response = await integration_client.put(
            f"{test_settings.API}/users/{user_id}/cart/items/{uuid4()}",
            json={"quantity": 7},
        )

        assert response.status_code == 404


class TestRemoveCartItemIntegration:
    async def test_remove_item_from_cart(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        add_response = await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )
        item_id = add_response.json()["items"][0]["id"]

        response = await integration_client.delete(
            f"{test_settings.API}/users/{user_id}/cart/items/{item_id}"
        )

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_remove_nonexistent_item_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )

        response = await integration_client.delete(
            f"{test_settings.API}/users/{user_id}/cart/items/{uuid4()}"
        )

        assert response.status_code == 404


class TestClearCartIntegration:
    async def test_clear_cart_returns_204(
        self, integration_client: AsyncClient
    ) -> None:
        user_id = uuid4()
        await integration_client.post(
            f"{test_settings.API}/users/{user_id}/cart/items", json=_add_item_payload()
        )

        response = await integration_client.delete(f"{test_settings.API}/users/{user_id}/cart")

        assert response.status_code == 204

        summary_response = await integration_client.get(
            f"{test_settings.API}/users/{user_id}/cart/summary"
        )
        assert summary_response.json()["total_items"] == 0
