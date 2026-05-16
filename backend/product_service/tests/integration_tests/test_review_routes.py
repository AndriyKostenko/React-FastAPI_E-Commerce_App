"""
Integration tests for review routes.

Uses a real PostgreSQL test database (PRODUCT_SERVICE_TEST_DB).
A category and product are created first (FK dependencies) before each
review test. Every test starts with a clean database.
"""
from uuid import uuid4

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


async def _create_product(client: AsyncClient, category_id: str) -> dict:
    r = await client.post(
        f"{TEST_API}/products",
        json={
            "name": "review test product",
            "description": "A product created specifically to test reviews",
            "category_id": category_id,
            "brand": "reviewbrand",
            "quantity": 5,
            "price": "199.99",
            "in_stock": True,
        },
    )
    assert r.status_code == status.HTTP_201_CREATED
    return r.json()


async def _setup_product(client: AsyncClient) -> tuple[dict, dict]:
    """Create category + product; return (category, product) dicts."""
    category = await _create_category(client)
    product = await _create_product(client, category["id"])
    return category, product


async def _create_review(
    client: AsyncClient,
    product_id: str,
    user_id: str,
    *,
    comment: str = "Great product!",
    rating: float = 4.5,
) -> dict:
    return await client.post(
        f"{TEST_API}/products/{product_id}/users/{user_id}/reviews",
        json={"comment": comment, "rating": rating},
    )


async def _setup_review(
    client: AsyncClient,
    product_id: str,
    user_id: str,
) -> dict:
    r = await _create_review(client, product_id, user_id)
    assert r.status_code == status.HTTP_201_CREATED, r.text
    return r.json()


# ===========================================================================
# POST /api/v1/products/{product_id}/users/{user_id}/reviews
# ===========================================================================

class TestCreateReview:
    async def test_create_review_returns_201_and_schema(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())

        response = await _create_review(integration_client, product["id"], user_id)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["comment"] == "Great product!"
        assert body["rating"] == pytest.approx(4.5)
        assert body["product_id"] == product["id"]
        assert body["user_id"] == user_id
        assert "id" in body

    async def test_create_duplicate_review_returns_409(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())

        await _setup_review(integration_client, product["id"], user_id)
        response = await _create_review(integration_client, product["id"], user_id)
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_create_review_invalid_rating_returns_422(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        response = await integration_client.post(
            f"{TEST_API}/products/{product['id']}/users/{uuid4()}/reviews",
            json={"comment": "Bad rating", "rating": 10.0},  # > 5
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# GET /api/v1/reviews
# ===========================================================================

class TestGetAllReviews:
    async def test_returns_all_reviews(self, integration_client: AsyncClient):
        _, product = await _setup_product(integration_client)
        user_id_1 = str(uuid4())
        user_id_2 = str(uuid4())
        await _setup_review(integration_client, product["id"], user_id_1)
        await _setup_review(integration_client, product["id"], user_id_2)

        response = await integration_client.get(f"{TEST_API}/reviews")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body) == 2

    async def test_returns_404_when_no_reviews(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/reviews")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/reviews/{review_id}
# ===========================================================================

class TestGetReviewById:
    async def test_returns_review_by_id(self, integration_client: AsyncClient):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())
        review = await _setup_review(integration_client, product["id"], user_id)

        response = await integration_client.get(f"{TEST_API}/reviews/{review['id']}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == review["id"]

    async def test_returns_404_for_unknown_review(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/reviews/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/products/{product_id}/reviews
# ===========================================================================

class TestGetReviewsByProduct:
    async def test_returns_reviews_for_product(self, integration_client: AsyncClient):
        _, product = await _setup_product(integration_client)
        user_id_1 = str(uuid4())
        user_id_2 = str(uuid4())
        await _setup_review(integration_client, product["id"], user_id_1)
        await _setup_review(integration_client, product["id"], user_id_2)

        response = await integration_client.get(
            f"{TEST_API}/products/{product['id']}/reviews"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body) == 2
        assert all(r["product_id"] == product["id"] for r in body)

    async def test_returns_404_when_product_has_no_reviews(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        response = await integration_client.get(
            f"{TEST_API}/products/{product['id']}/reviews"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/users/{user_id}/reviews
# ===========================================================================

class TestGetReviewsByUser:
    async def test_returns_reviews_by_user(self, integration_client: AsyncClient):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())
        await _setup_review(integration_client, product["id"], user_id)

        response = await integration_client.get(f"{TEST_API}/users/{user_id}/reviews")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body) == 1
        assert body[0]["user_id"] == user_id

    async def test_returns_404_when_user_has_no_reviews(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(f"{TEST_API}/users/{uuid4()}/reviews")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/products/{product_id}/users/{user_id}/reviews
# ===========================================================================

class TestGetSpecificReview:
    async def test_returns_review_for_product_and_user(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())
        review = await _setup_review(integration_client, product["id"], user_id)

        response = await integration_client.get(
            f"{TEST_API}/products/{product['id']}/users/{user_id}/reviews"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == review["id"]

    async def test_returns_404_when_not_found(self, integration_client: AsyncClient):
        _, product = await _setup_product(integration_client)
        response = await integration_client.get(
            f"{TEST_API}/products/{product['id']}/users/{uuid4()}/reviews"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# PUT /api/v1/products/{product_id}/users/{user_id}/reviews
# ===========================================================================

class TestUpdateReview:
    async def test_update_review_comment_and_rating(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())
        await _setup_review(integration_client, product["id"], user_id)

        response = await integration_client.put(
            f"{TEST_API}/products/{product['id']}/users/{user_id}/reviews",
            json={"comment": "Updated comment", "rating": 2.5},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["comment"] == "Updated comment"
        assert body["rating"] == pytest.approx(2.5)

    async def test_update_nonexistent_review_returns_404(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        response = await integration_client.put(
            f"{TEST_API}/products/{product['id']}/users/{uuid4()}/reviews",
            json={"rating": 1.0},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# DELETE /api/v1/products/{product_id}/users/{user_id}/reviews
# ===========================================================================

class TestDeleteReview:
    async def test_delete_review_returns_204(self, integration_client: AsyncClient):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())
        await _setup_review(integration_client, product["id"], user_id)

        response = await integration_client.delete(
            f"{TEST_API}/products/{product['id']}/users/{user_id}/reviews"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_deleted_review_not_found_on_fetch(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        user_id = str(uuid4())
        await _setup_review(integration_client, product["id"], user_id)

        await integration_client.delete(
            f"{TEST_API}/products/{product['id']}/users/{user_id}/reviews"
        )
        response = await integration_client.get(
            f"{TEST_API}/products/{product['id']}/users/{user_id}/reviews"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_nonexistent_review_returns_404(
        self, integration_client: AsyncClient
    ):
        _, product = await _setup_product(integration_client)
        response = await integration_client.delete(
            f"{TEST_API}/products/{product['id']}/users/{uuid4()}/reviews"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
