"""Unit tests for product proxy routes — auth requirements and gateway delegation."""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.constants import (
    TEST_PRODUCT_ID, TEST_CATEGORY_ID, TEST_IMAGE_ID, TEST_REVIEW_ID,
    TEST_USER_ID, TEST_API,
)


class TestPublicProductRoutes:
    async def test_get_all_products_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/products")
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_get_product_by_id_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/products/{TEST_PRODUCT_ID}")
        mock_forward.assert_awaited_once()

    async def test_get_products_detailed_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/products/detailed")
        mock_forward.assert_awaited_once()

    async def test_get_all_categories_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/categories")
        mock_forward.assert_awaited_once()

    async def test_get_category_by_id_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/categories/{TEST_CATEGORY_ID}")
        mock_forward.assert_awaited_once()

    async def test_get_all_images_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/images")
        mock_forward.assert_awaited_once()

    async def test_generate_custom_image_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.post(
            f"{TEST_API}/images/generations",
            json={"prompt": "Neon tiger design", "style": "Streetwear"},
        )
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_get_all_reviews_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/reviews")
        mock_forward.assert_awaited_once()

    async def test_get_product_reviews_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/products/{TEST_PRODUCT_ID}/reviews")
        mock_forward.assert_awaited_once()


class TestAdminProductRoutes:
    async def test_create_product_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.post(f"{TEST_API}/products", json={"name": "Widget"})
        mock_forward.assert_awaited_once()

    async def test_create_product_as_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(f"{TEST_API}/products", json={"name": "Widget"})
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_update_product_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.patch(f"{TEST_API}/products/{TEST_PRODUCT_ID}", json={"name": "Updated"})
        mock_forward.assert_awaited_once()

    async def test_update_product_as_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.patch(f"{TEST_API}/products/{TEST_PRODUCT_ID}", json={})
        assert response.status_code == 403

    async def test_delete_product_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.delete(f"{TEST_API}/products/{TEST_PRODUCT_ID}")
        mock_forward.assert_awaited_once()

    async def test_delete_product_as_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.delete(f"{TEST_API}/products/{TEST_PRODUCT_ID}")
        assert response.status_code == 403

    async def test_create_category_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.post(f"{TEST_API}/categories", json={"name": "Electronics"})
        mock_forward.assert_awaited_once()

    async def test_delete_category_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.delete(f"{TEST_API}/categories/{TEST_CATEGORY_ID}")
        mock_forward.assert_awaited_once()

    async def test_delete_image_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.delete(f"{TEST_API}/images/{TEST_IMAGE_ID}")
        mock_forward.assert_awaited_once()

    async def test_admin_schema_products_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/admin/schema/products")
        mock_forward.assert_awaited_once()


class TestAuthenticatedProductRoutes:
    async def test_create_review_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(
            f"{TEST_API}/products/{TEST_PRODUCT_ID}/users/{TEST_USER_ID}/reviews",
            json={"rating": 5, "comment": "Great!"},
        )
        mock_forward.assert_awaited_once()

    async def test_add_to_favorites_authenticated_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(f"{TEST_API}/products/{TEST_PRODUCT_ID}/favorite")
        mock_forward.assert_awaited_once()
