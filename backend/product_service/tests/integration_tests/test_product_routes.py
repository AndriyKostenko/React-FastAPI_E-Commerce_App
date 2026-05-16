"""
Integration tests for product routes.

Uses a real PostgreSQL test database (PRODUCT_SERVICE_TEST_DB).
A category is created first (FK dependency) and used across all product tests.
Every test starts with a clean database (truncated after each test).
"""
from uuid import uuid4
from decimal import Decimal

import pytest
from fastapi import status
from httpx import AsyncClient

TEST_API = "/api/v1"

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

async def _create_category(client: AsyncClient, *, name: str = "electronics") -> dict:
    r = await client.post(f"{TEST_API}/categories", json={"name": name})
    assert r.status_code == status.HTTP_201_CREATED
    return r.json()


async def _create_product(
    client: AsyncClient,
    category_id: str,
    *,
    name: str = "test laptop",
    description: str = "A high-quality test laptop for integration testing",
    brand: str = "testbrand",
    quantity: int = 10,
    price: str = "999.99",
    in_stock: bool = True,
) -> dict:
    payload = {
        "name": name,
        "description": description,
        "category_id": category_id,
        "brand": brand,
        "quantity": quantity,
        "price": price,
        "in_stock": in_stock,
    }
    return await client.post(f"{TEST_API}/products", json=payload)


async def _setup_product(
    client: AsyncClient,
    category_id: str,
    *,
    name: str = "test laptop",
) -> dict:
    """Create product and return response JSON, asserting 201."""
    r = await _create_product(client, category_id, name=name)
    assert r.status_code == status.HTTP_201_CREATED, r.text
    return r.json()


# ===========================================================================
# POST /api/v1/products
# ===========================================================================

class TestCreateProduct:
    async def test_create_product_returns_201_and_schema(
        self, integration_client: AsyncClient
    ):
        category = await _create_category(integration_client)
        response = await _create_product(integration_client, category["id"])

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "test laptop"
        assert body["brand"] == "testbrand"
        assert body["category_id"] == category["id"]
        assert "id" in body
        assert "date_created" in body

    async def test_name_and_brand_are_lowercased(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        response = await _create_product(
            integration_client, category["id"], name="DELL XPS", brand="DELL"
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "dell xps"
        assert body["brand"] == "dell"

    async def test_create_duplicate_product_returns_400(
        self, integration_client: AsyncClient
    ):
        category = await _create_category(integration_client)
        await _setup_product(integration_client, category["id"], name="duplicate")
        response = await _create_product(integration_client, category["id"], name="duplicate")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_product_invalid_category_returns_400(
        self, integration_client: AsyncClient
    ):
        response = await _create_product(integration_client, str(uuid4()))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_product_invalid_payload_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{TEST_API}/products", json={"name": "too short"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# GET /api/v1/products
# ===========================================================================

class TestGetAllProducts:
    async def test_returns_list_of_products(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        await _setup_product(integration_client, category["id"], name="laptop one")
        await _setup_product(integration_client, category["id"], name="laptop two")

        response = await integration_client.get(f"{TEST_API}/products")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2

    async def test_returns_404_when_no_products(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/products")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_filter_by_in_stock(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        await _setup_product(integration_client, category["id"], name="in stock item", in_stock=True)
        await _create_product(integration_client, category["id"], name="out of stock item", in_stock=False)

        response = await integration_client.get(
            f"{TEST_API}/products", params={"in_stock": "true"}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert all(p["in_stock"] for p in body)


# ===========================================================================
# GET /api/v1/products/{product_id}
# ===========================================================================

class TestGetProductById:
    async def test_returns_product_by_id(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        response = await integration_client.get(f"{TEST_API}/products/{product_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == product_id

    async def test_returns_404_for_unknown_id(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/products/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/products/{product_id}/detailed
# ===========================================================================

class TestGetProductDetailed:
    async def test_returns_product_with_relations(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        response = await integration_client.get(
            f"{TEST_API}/products/{product_id}/detailed"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "images" in body
        assert "reviews" in body
        assert "category" in body


# ===========================================================================
# PATCH /api/v1/products/{product_id}
# ===========================================================================

class TestUpdateProduct:
    async def test_update_product_quantity(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        response = await integration_client.patch(
            f"{TEST_API}/products/{product_id}",
            json={"quantity": 50},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["quantity"] == 50

    async def test_update_product_price(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        response = await integration_client.patch(
            f"{TEST_API}/products/{product_id}",
            json={"price": "1299.99"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert float(response.json()["price"]) == pytest.approx(1299.99)

    async def test_update_nonexistent_product_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.patch(
            f"{TEST_API}/products/{uuid4()}",
            json={"quantity": 1},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_with_invalid_category_returns_400(
        self, integration_client: AsyncClient
    ):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        response = await integration_client.patch(
            f"{TEST_API}/products/{product_id}",
            json={"category_id": str(uuid4())},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ===========================================================================
# DELETE /api/v1/products/{product_id}
# ===========================================================================

class TestDeleteProduct:
    async def test_delete_product_returns_204(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        response = await integration_client.delete(f"{TEST_API}/products/{product_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_deleted_product_not_found_on_fetch(
        self, integration_client: AsyncClient
    ):
        category = await _create_category(integration_client)
        product = await _setup_product(integration_client, category["id"])
        product_id = product["id"]

        await integration_client.delete(f"{TEST_API}/products/{product_id}")
        response = await integration_client.get(f"{TEST_API}/products/{product_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_nonexistent_product_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.delete(f"{TEST_API}/products/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
