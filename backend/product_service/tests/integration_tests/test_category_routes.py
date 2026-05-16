"""
Integration tests for category routes.

Uses a real PostgreSQL test database (PRODUCT_SERVICE_TEST_DB).
Every test starts with a clean database (truncated after each test).

Module-level helpers keep test methods concise.
"""
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

TEST_API = "/api/v1"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

async def _create_category(
    client: AsyncClient,
    *,
    name: str = "electronics",
) -> dict:
    response = await client.post(
        f"{TEST_API}/categories",
        json={"name": name},
    )
    return response


async def _setup_category(client: AsyncClient, *, name: str = "electronics") -> dict:
    """Create category and return its response JSON."""
    r = await _create_category(client, name=name)
    assert r.status_code == status.HTTP_201_CREATED
    return r.json()


# ===========================================================================
# GET /health
# ===========================================================================

class TestHealthEndpoint:
    async def test_health_returns_ok(self, integration_client: AsyncClient):
        response = await integration_client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"


# ===========================================================================
# POST /api/v1/categories
# ===========================================================================

class TestCreateCategory:
    async def test_create_category_returns_201_and_schema(
        self, integration_client: AsyncClient
    ):
        response = await _create_category(integration_client)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "electronics"
        assert "id" in body
        assert "date_created" in body

    async def test_create_category_name_is_lowercased(
        self, integration_client: AsyncClient
    ):
        response = await _create_category(integration_client, name="Home Appliances")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "home appliances"

    async def test_create_duplicate_category_returns_error(
        self, integration_client: AsyncClient
    ):
        await _setup_category(integration_client, name="audio")
        response = await _create_category(integration_client, name="audio")
        # CategoryCreationError maps to 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_create_category_invalid_payload_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(f"{TEST_API}/categories", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# GET /api/v1/categories
# ===========================================================================

class TestGetAllCategories:
    async def test_returns_list_of_categories(self, integration_client: AsyncClient):
        await _setup_category(integration_client, name="books")
        await _setup_category(integration_client, name="clothing")

        response = await integration_client.get(f"{TEST_API}/categories")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2

    async def test_returns_404_when_no_categories(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/categories")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/categories/{category_id}
# ===========================================================================

class TestGetCategoryById:
    async def test_returns_category_by_id(self, integration_client: AsyncClient):
        category = await _setup_category(integration_client)
        category_id = category["id"]

        response = await integration_client.get(f"{TEST_API}/categories/{category_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == category_id

    async def test_returns_404_for_unknown_id(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/categories/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# PATCH /api/v1/categories/{category_id}
# ===========================================================================

class TestUpdateCategory:
    async def test_update_category_name(self, integration_client: AsyncClient):
        category = await _setup_category(integration_client, name="oldname")
        category_id = category["id"]

        response = await integration_client.patch(
            f"{TEST_API}/categories/{category_id}",
            data={"name": "newname"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "newname"

    async def test_update_nonexistent_category_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.patch(
            f"{TEST_API}/categories/{uuid4()}",
            data={"name": "anything"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# DELETE /api/v1/categories/{category_id}
# ===========================================================================

class TestDeleteCategory:
    async def test_delete_category_returns_204(self, integration_client: AsyncClient):
        category = await _setup_category(integration_client)
        category_id = category["id"]

        response = await integration_client.delete(f"{TEST_API}/categories/{category_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_deleted_category_not_found_on_fetch(
        self, integration_client: AsyncClient
    ):
        category = await _setup_category(integration_client)
        category_id = category["id"]

        await integration_client.delete(f"{TEST_API}/categories/{category_id}")
        response = await integration_client.get(f"{TEST_API}/categories/{category_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_nonexistent_category_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.delete(f"{TEST_API}/categories/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
