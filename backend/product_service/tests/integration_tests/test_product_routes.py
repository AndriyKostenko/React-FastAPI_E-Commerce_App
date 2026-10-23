"""
Integration tests for product routes.

Uses a real PostgreSQL test database (PRODUCT_SERVICE_TEST_DB).
A category is created first (FK dependency) and used across all product tests.
Every test starts with a clean database (truncated after each test).
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from decimal import Decimal

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import update

from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.product_models import Product
from models.product_variant_models import ProductVariant

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
    image_url: str | None = None,
    images: list[str] | None = None,
    variants: list[dict] | None = None,
    variant_option_names: list[str] | None = None,
) -> dict:
    payload = {
        "name": name,
        "description": description,
        "category_id": category_id,
        "brand": brand,
        "quantity": quantity,
        "price": price,
        "in_stock": in_stock,
        "image_url": image_url,
        "images": images,
        "variants": variants,
        "variant_option_names": variant_option_names or [],
    }
    return await client.post(f"{TEST_API}/products", json=payload)


async def _setup_product(
    client: AsyncClient,
    category_id: str,
    *,
    name: str = "test laptop",
    **kwargs,
) -> dict:
    """Create product and return response JSON, asserting 201."""
    r = await _create_product(client, category_id, name=name, **kwargs)
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
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


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

    async def test_returns_empty_list_when_no_products(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/products")
        assert response.status_code == 200
        assert response.json() == []

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
# GET /api/v1/products/cards (and search on the product lists)
# ===========================================================================

async def _set_variant_active(manager: TestDatabaseSessionManager, variant_key: str, active: bool) -> None:
    async with manager.transaction() as session:
        await session.execute(
            update(ProductVariant).where(ProductVariant.variant_key == variant_key).values(active=active)
        )


async def _set_date_created(manager: TestDatabaseSessionManager, product_ids: list[str], when: datetime) -> None:
    async with manager.transaction() as session:
        await session.execute(
            update(Product).where(Product.id.in_([UUID(pid) for pid in product_ids])).values(date_created=when)
        )


class TestGetProductCards:
    async def test_card_carries_only_what_the_shop_reads(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ):
        category = await _create_category(integration_client, name="t-shirts")
        product = await _setup_product(
            integration_client,
            category["id"],
            name="black tee",
            image_url="https://cdn.example.com/main.jpg",
            images=["https://cdn.example.com/gallery.jpg"],
            variants=[{"vid": "v-black-m", "variant_key": "Black-M"}, {"vid": "v-white-l", "variant_key": "White-L"}],
            variant_option_names=["Color", "Size"],
        )
        await _set_variant_active(test_database_session_manager, "White-L", False)
        rated = await integration_client.post(
            f"{TEST_API}/products/{product['id']}/users/{uuid4()}/reviews", json={"comment": "Fits well", "rating": 4}
        )
        unrated = await integration_client.post(
            f"{TEST_API}/products/{product['id']}/users/{uuid4()}/reviews", json={"comment": "No stars given"}
        )
        assert rated.status_code == unrated.status_code == status.HTTP_201_CREATED

        response = await integration_client.get(f"{TEST_API}/products/cards")

        assert response.status_code == status.HTTP_200_OK
        [card] = response.json()
        assert set(card) == {
            "id", "supplier_id", "name", "price", "in_stock", "image_url",
            "date_created", "category", "reviews", "variants", "variant_option_names",
        }
        assert card["id"] == product["id"]
        assert card["image_url"] == "https://cdn.example.com/main.jpg"
        assert card["category"] == {"id": category["id"], "name": "t-shirts"}
        # Inactive variants and unrated reviews are left out.
        assert card["variants"] == [{"variant_key": "Black-M", "active": True}]
        assert card["reviews"] == [{"rating": 4.0}]
        # The shop filters read each key's parts by these names.
        assert card["variant_option_names"] == ["Color", "Size"]

    async def test_card_without_a_main_image_shows_the_first_gallery_image(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        await _setup_product(integration_client, category["id"], images=["https://cdn.example.com/only.jpg"])

        [card] = (await integration_client.get(f"{TEST_API}/products/cards")).json()

        assert card["image_url"] == "https://cdn.example.com/only.jpg"

    async def test_search_term_matches_name_description_or_brand(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        hoodie = await _setup_product(integration_client, category["id"], name="red hoodie")
        tee = await _setup_product(integration_client, category["id"], name="blue tee", description="Soft cotton jersey")
        branded = await _setup_product(integration_client, category["id"], name="green polo", brand="acmewear")

        async def found(term: str) -> set[str]:
            response = await integration_client.get(f"{TEST_API}/products/cards", params={"search_term": term})
            assert response.status_code == status.HTTP_200_OK
            return {card["id"] for card in response.json()}

        assert await found("hoodie") == {hoodie["id"]}
        assert await found("COTTON") == {tee["id"]}
        assert await found("acme") == {branded["id"]}
        assert await found("zzqqxx") == set()

    async def test_category_id_narrows_the_cards(self, integration_client: AsyncClient):
        shirts = await _create_category(integration_client, name="shirts")
        mugs = await _create_category(integration_client, name="mugs")
        shirt = await _setup_product(integration_client, shirts["id"], name="plain shirt")
        await _setup_product(integration_client, mugs["id"], name="plain mug")

        response = await integration_client.get(f"{TEST_API}/products/cards", params={"category_id": shirts["id"]})

        assert [card["id"] for card in response.json()] == [shirt["id"]]

    async def test_equal_timestamps_page_in_id_order(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ):
        # A sync writes many products in one transaction, so they share date_created.
        category = await _create_category(integration_client)
        ids = [(await _setup_product(integration_client, category["id"], name=f"synced tee {n}"))["id"] for n in range(3)]
        await _set_date_created(test_database_session_manager, ids, datetime(2026, 10, 19, tzinfo=timezone.utc))

        pages = [
            (await integration_client.get(
                f"{TEST_API}/products/cards",
                params={"sort_by": "date_created", "sort_order": "desc", "limit": 1, "offset": offset},
            )).json()
            for offset in range(3)
        ]

        assert [card["id"] for [card] in pages] == sorted(ids)

    async def test_limit_above_500_is_rejected(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/products/cards", params={"limit": 501})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_detailed_list_honours_the_search_term(self, integration_client: AsyncClient):
        category = await _create_category(integration_client)
        hoodie = await _setup_product(integration_client, category["id"], name="red hoodie")
        await _setup_product(integration_client, category["id"], name="blue tee")

        response = await integration_client.get(f"{TEST_API}/products/detailed", params={"search_term": "hoodie"})

        assert [product["id"] for product in response.json()] == [hoodie["id"]]


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
