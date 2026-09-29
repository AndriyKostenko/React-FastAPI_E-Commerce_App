"""
The hourly CJ stock refresh, on product-service's side, against the real test
database: the product is imported through the real import path, then stock
levels arrive through the real consumer.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from event_consumer.product_event_consumer import ProductEventConsumer
from models.product_models import Product
from resources import settings
from shared.contracts.events import SupplierProductsFetchedEvent, SupplierStockUpdatedEvent
from shared.contracts.supplier import GenericSupplierProduct, SupplierProductVariant, SupplierStockLevel
from shared.testing.signing_keys import ANONYMOUS, EphemeralSigningKeys
from tests.conftest import DEFAULT_CALLER, SIGNING_KEYS, TEST_API

T0 = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _consumer(db) -> ProductEventConsumer:
    cache = MagicMock()
    cache.invalidate_namespace = AsyncMock()
    return ProductEventConsumer(
        logger=MagicMock(), database=db, idempotency_service=MagicMock(),
        cache_manager=cache, publisher=MagicMock(), settings=settings,
    )


async def _import(db, pid: str = "pid-1", *, supplier_id: str = "cjdropshipping") -> None:
    product = GenericSupplierProduct(
        supplier_id=supplier_id, supplier_pid=pid, supplier_category_id="cj-tshirt",
        category_name="t-shirts", name=f"Tee {pid}", description="shirt", price=Decimal("12.50"),
        quantity=12, in_stock=True,
        variants=[
            SupplierProductVariant(vid=f"{pid}-S", variant_sku="S", inventory_num=7),
            SupplierProductVariant(vid=f"{pid}-M", variant_sku="M", inventory_num=5),
        ],
    )
    await _consumer(db).handle_supplier_products_fetched(SupplierProductsFetchedEvent(
        supplier_id=supplier_id, fetch_id=uuid4(), batch_number=1, total_batches=1, products=[product],
    ).model_dump(mode="json"))


async def _stock(db, measured_at: datetime, **levels: dict[str, int]) -> None:
    event = SupplierStockUpdatedEvent(
        supplier_id="cjdropshipping",
        measured_at=measured_at,
        levels=[SupplierStockLevel(supplier_pid=pid, variants=variants) for pid, variants in levels.items()],
    )
    await _consumer(db).handle_supplier_stock_updated(event.model_dump(mode="json"))


async def _product(db, pid: str = "pid-1") -> Product:
    async with db.transaction() as session:
        return (await session.execute(
            select(Product).where(Product.pid == pid).options(selectinload(Product.variants))
        )).scalar_one()


def _variant_stock(product: Product) -> dict[str, int | None]:
    return {v.vid: v.inventory_num for v in product.variants}


@pytest.fixture
async def db(test_database_session_manager):
    await test_database_session_manager.truncate_all_tables(Product.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Product.metadata)


# ------------------------------------------------------------------ applying


async def test_a_product_sold_out_in_the_us_goes_out_of_stock(db) -> None:
    """The bug this fixes: the catalogue sync never sees it again, the refresh does."""
    await _import(db)

    await _stock(db, T0, **{"pid-1": {"pid-1-S": 0, "pid-1-M": 0}})

    product = await _product(db)
    assert (product.quantity, product.in_stock) == (0, False)
    assert _variant_stock(product) == {"pid-1-S": 0, "pid-1-M": 0}
    assert product.stock_checked_at == T0


async def test_stock_is_set_per_size_and_totals_follow(db) -> None:
    await _import(db)

    await _stock(db, T0, **{"pid-1": {"pid-1-S": 3, "pid-1-M": 0}})

    product = await _product(db)
    assert _variant_stock(product) == {"pid-1-S": 3, "pid-1-M": 0}
    assert (product.quantity, product.in_stock) == (3, True)


async def test_a_sold_out_product_comes_back_when_cj_restocks(db) -> None:
    await _import(db)
    await _stock(db, T0, **{"pid-1": {"pid-1-S": 0, "pid-1-M": 0}})

    await _stock(db, T0 + timedelta(hours=1), **{"pid-1": {"pid-1-S": 4, "pid-1-M": 2}})

    product = await _product(db)
    assert (product.quantity, product.in_stock) == (6, True)


async def test_an_older_measurement_arriving_late_changes_nothing(db) -> None:
    """A retried or redelivered batch must not move stock back in time."""
    await _import(db)
    await _stock(db, T0 + timedelta(hours=1), **{"pid-1": {"pid-1-S": 0, "pid-1-M": 0}})

    await _stock(db, T0, **{"pid-1": {"pid-1-S": 9, "pid-1-M": 9}})

    product = await _product(db)
    assert (product.quantity, product.in_stock) == (0, False)
    assert product.stock_checked_at == T0 + timedelta(hours=1)


async def test_a_product_deleted_since_it_was_asked_about_is_skipped(db) -> None:
    await _import(db)

    await _stock(db, T0, **{"gone": {"gone-S": 5}, "pid-1": {"pid-1-S": 1, "pid-1-M": 1}})

    assert (await _product(db)).quantity == 2


# -------------------------------------------------------------- stock keys


async def test_supplier_service_is_told_every_cj_product_we_sell(integration_client: AsyncClient, db) -> None:
    await _import(db, "pid-1")
    await _import(db, "pid-2")
    await _import(db, "other-1", supplier_id="another-supplier")

    response = await integration_client.get(
        f"{TEST_API}/products/stock-keys/cjdropshipping", auth=SIGNING_KEYS.supplier_service_auth()
    )

    assert response.status_code == 200, response.text
    assert response.json() == [
        {"supplier_pid": "pid-1", "vids": ["pid-1-M", "pid-1-S"]},
        {"supplier_pid": "pid-2", "vids": ["pid-2-M", "pid-2-S"]},
    ]


@pytest.mark.parametrize(
    ("caller", "why"),
    [
        (ANONYMOUS, "anyone who reaches the service directly"),
        (DEFAULT_CALLER, "a user, even an admin, through the gateway"),
        (SIGNING_KEYS.order_service_auth(), "another service"),
        (EphemeralSigningKeys().supplier_service_auth(), "someone without supplier-service's key"),
    ],
    ids=["anonymous", "admin-user", "order-service", "forged-key"],
)
async def test_only_supplier_service_may_list_them(integration_client: AsyncClient, caller, why: str) -> None:
    response = await integration_client.get(f"{TEST_API}/products/stock-keys/cjdropshipping", auth=caller)
    assert response.status_code == 401, why
