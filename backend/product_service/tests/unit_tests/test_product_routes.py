"""
Route-level unit tests for product_service endpoints.

Uses httpx.AsyncClient + ASGITransport to send real HTTP requests through
the FastAPI application without any live infrastructure:
  - App lifespan is replaced with a no-op (no DB/Redis/RabbitMQ connections).
  - All service dependencies are overridden via app.dependency_overrides.

Error branches configure the mock services to raise the appropriate
exception via .side_effect.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from exceptions.category_exceptions import CategoryCreationError, CategoryNotFoundError
from exceptions.product_exceptions import ProductCreationError, ProductNotFoundError
from exceptions.review_exceptions import ReviewAlreadyExistsError, ReviewNotFoundError
from tests.conftest import TEST_API, TEST_PRODUCT_ID, TEST_CATEGORY_ID, TEST_USER_ID, TEST_REVIEW_ID


# ===========================================================================
# GET /health
# ===========================================================================

class TestHealthEndpoint:
    async def test_health_returns_ok(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get("/health")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ok"


# ===========================================================================
# POST /api/v1/products
# ===========================================================================

class TestCreateProductEndpoint:
    _payload = {
        "name": "Test Laptop",
        "description": "A high-quality test laptop for testing purposes",
        "category_id": str(TEST_CATEGORY_ID),
        "brand": "TestBrand",
        "quantity": 5,
        "price": "499.99",
        "in_stock": True,
    }

    async def test_create_product_returns_201(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.post(f"{TEST_API}/products", json=self._payload)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "test laptop"

    async def test_create_product_duplicate_returns_400(
        self, client_for_unit_testing: AsyncClient, mock_route_product_service
    ):
        mock_route_product_service.create_product_item = AsyncMock(
            side_effect=ProductCreationError("Already exists")
        )
        response = await client_for_unit_testing.post(f"{TEST_API}/products", json=self._payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_product_invalid_payload_returns_422(
        self, client_for_unit_testing: AsyncClient
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/products", json={"name": "x"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# GET /api/v1/products
# ===========================================================================

class TestGetAllProductsEndpoint:
    async def test_get_all_products_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(f"{TEST_API}/products")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1

    async def test_get_all_products_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_product_service
    ):
        mock_route_product_service.get_all_products_without_relations = AsyncMock(
            side_effect=ProductNotFoundError("No products found")
        )
        response = await client_for_unit_testing.get(f"{TEST_API}/products")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/products/{product_id}
# ===========================================================================

class TestGetProductByIdEndpoint:
    async def test_get_product_by_id_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(f"{TEST_API}/products/{TEST_PRODUCT_ID}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == str(TEST_PRODUCT_ID)

    async def test_get_product_by_id_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_product_service
    ):
        mock_route_product_service.get_product_by_id_without_relations = AsyncMock(
            side_effect=ProductNotFoundError("Product not found")
        )
        response = await client_for_unit_testing.get(f"{TEST_API}/products/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# PATCH /api/v1/products/{product_id}
# ===========================================================================

class TestUpdateProductEndpoint:
    async def test_update_product_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/products/{TEST_PRODUCT_ID}",
            json={"quantity": 20},
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_update_product_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_product_service
    ):
        mock_route_product_service.update_product = AsyncMock(
            side_effect=ProductNotFoundError("Product not found")
        )
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/products/{uuid4()}",
            json={"quantity": 5},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# DELETE /api/v1/products/{product_id}
# ===========================================================================

class TestDeleteProductEndpoint:
    async def test_delete_product_returns_204(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/products/{TEST_PRODUCT_ID}"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_product_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_product_service
    ):
        mock_route_product_service.delete_product_by_id = AsyncMock(
            side_effect=ProductNotFoundError("Not found")
        )
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/products/{uuid4()}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# POST /api/v1/categories
# ===========================================================================

class TestCreateCategoryEndpoint:
    _payload = {"name": "Electronics"}

    async def test_create_category_returns_201(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/categories", json=self._payload
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "electronics"

    async def test_create_category_duplicate_returns_500(
        self, client_for_unit_testing: AsyncClient, mock_route_category_service
    ):
        mock_route_category_service.create_category = AsyncMock(
            side_effect=CategoryCreationError("Already exists")
        )
        response = await client_for_unit_testing.post(
            f"{TEST_API}/categories", json=self._payload
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ===========================================================================
# GET /api/v1/categories
# ===========================================================================

class TestGetAllCategoriesEndpoint:
    async def test_get_all_categories_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(f"{TEST_API}/categories")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1

    async def test_get_all_categories_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_category_service
    ):
        mock_route_category_service.get_all_categories = AsyncMock(
            side_effect=CategoryNotFoundError("No categories")
        )
        response = await client_for_unit_testing.get(f"{TEST_API}/categories")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/categories/{category_id}
# ===========================================================================

class TestGetCategoryByIdEndpoint:
    async def test_get_category_by_id_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/categories/{TEST_CATEGORY_ID}"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == str(TEST_CATEGORY_ID)

    async def test_get_category_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_category_service
    ):
        mock_route_category_service.get_category_by_id = AsyncMock(
            side_effect=CategoryNotFoundError("Not found")
        )
        response = await client_for_unit_testing.get(
            f"{TEST_API}/categories/{uuid4()}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# DELETE /api/v1/categories/{category_id}
# ===========================================================================

class TestDeleteCategoryEndpoint:
    async def test_delete_category_returns_204(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/categories/{TEST_CATEGORY_ID}"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_category_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_category_service
    ):
        mock_route_category_service.delete_category = AsyncMock(
            side_effect=CategoryNotFoundError("Not found")
        )
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/categories/{uuid4()}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# POST /api/v1/products/{product_id}/users/{user_id}/reviews
# ===========================================================================

class TestCreateReviewEndpoint:
    _payload = {"comment": "Fantastic!", "rating": 4.5}

    async def test_create_review_returns_201(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/products/{TEST_PRODUCT_ID}/users/{TEST_USER_ID}/reviews",
            json=self._payload,
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["comment"] == "Great product!"

    async def test_create_review_duplicate_returns_409(
        self, client_for_unit_testing: AsyncClient, mock_route_review_service
    ):
        mock_route_review_service.create_product_review = AsyncMock(
            side_effect=ReviewAlreadyExistsError("Already reviewed")
        )
        response = await client_for_unit_testing.post(
            f"{TEST_API}/products/{TEST_PRODUCT_ID}/users/{TEST_USER_ID}/reviews",
            json=self._payload,
        )
        assert response.status_code == status.HTTP_409_CONFLICT


# ===========================================================================
# GET /api/v1/reviews
# ===========================================================================

class TestGetAllReviewsEndpoint:
    async def test_get_all_reviews_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(f"{TEST_API}/reviews")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1

    async def test_get_all_reviews_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_review_service
    ):
        mock_route_review_service.get_all_reviews = AsyncMock(
            side_effect=ReviewNotFoundError("No reviews")
        )
        response = await client_for_unit_testing.get(f"{TEST_API}/reviews")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/reviews/{review_id}
# ===========================================================================

class TestGetReviewByIdEndpoint:
    async def test_get_review_by_id_returns_200(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(f"{TEST_API}/reviews/{TEST_REVIEW_ID}")
        assert response.status_code == status.HTTP_200_OK

    async def test_get_review_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_review_service
    ):
        mock_route_review_service.get_review_by_id = AsyncMock(
            side_effect=ReviewNotFoundError("Not found")
        )
        response = await client_for_unit_testing.get(f"{TEST_API}/reviews/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# DELETE /api/v1/products/{product_id}/users/{user_id}/reviews
# ===========================================================================

class TestDeleteReviewEndpoint:
    async def test_delete_review_returns_204(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/products/{TEST_PRODUCT_ID}/users/{TEST_USER_ID}/reviews"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_review_not_found_returns_404(
        self, client_for_unit_testing: AsyncClient, mock_route_review_service
    ):
        mock_route_review_service.get_review_by_product_id_and_user_id = AsyncMock(
            side_effect=ReviewNotFoundError("Not found")
        )
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/products/{uuid4()}/users/{uuid4()}/reviews"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
