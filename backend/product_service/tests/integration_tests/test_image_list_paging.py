"""GET /images pages through every product's images, newest first (the admin panel's Images list)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient

from models.category_models import ProductCategory
from models.product_image_models import ProductImage
from models.product_models import Product
from shared.managers.test_database_session_manager import TestDatabaseSessionManager

IMAGES = "/api/v1/images"


async def _seed_images(db: TestDatabaseSessionManager, count: int) -> list[str]:
    """`count` images one minute apart; their file names, newest first."""
    now = datetime.now(timezone.utc)
    async with db.transaction() as session:
        category = ProductCategory(name=f"tees-{uuid4().hex[:6]}")
        session.add(category)
        await session.flush()
        product = Product(id=uuid4(), name="Tee", category_id=category.id, brand="Brand",
                          quantity=1, price=Decimal("10.00"), in_stock=True)
        session.add(product)
        await session.flush()
        session.add_all([
            ProductImage(product_id=product.id, image_url=f"catalogue/test/{i}.jpg",
                         date_created=now - timedelta(minutes=count - i))
            for i in range(count)
        ])
    return [f"{i}.jpg" for i in reversed(range(count))]


def _names(rows: list[dict[str, str]]) -> list[str]:
    # Responses add the public origin to the stored key; the file name identifies the image.
    return [row["image_url"].rsplit("/", 1)[-1] for row in rows]


async def test_pages_newest_first(integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager) -> None:
    newest_first = await _seed_images(test_database_session_manager, 5)

    first = await integration_client.get(IMAGES, params={"limit": 2})
    second = await integration_client.get(IMAGES, params={"limit": 2, "offset": 2})
    last = await integration_client.get(IMAGES, params={"limit": 2, "offset": 4})

    assert first.status_code == second.status_code == last.status_code == 200
    assert _names(first.json()) == newest_first[0:2]
    assert _names(second.json()) == newest_first[2:4]
    assert _names(last.json()) == newest_first[4:5]


async def test_page_size_is_bounded(integration_client: AsyncClient) -> None:
    assert (await integration_client.get(IMAGES, params={"limit": 0})).status_code == 422
    assert (await integration_client.get(IMAGES, params={"limit": 101})).status_code == 422
    assert (await integration_client.get(IMAGES, params={"offset": -1})).status_code == 422
