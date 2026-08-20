from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from event_consumer.product_event_consumer import ProductEventConsumer
from models.outbox_models import OutboxEvent
from models.product_models import Product
from models.supplier_import_models import SupplierImportBatch
from resources import settings
from shared.contracts.events import SupplierProductsFetchedEvent
from shared.contracts.supplier import GenericSupplierProduct, SupplierProductVariant


async def test_supplier_batch_is_atomic_idempotent_and_reconciles_children(
    test_database_session_manager,
) -> None:
    await test_database_session_manager.truncate_all_tables(Product.metadata)
    cache = MagicMock()
    cache.invalidate_namespace = AsyncMock()
    consumer = ProductEventConsumer(
        logger=MagicMock(),
        database=test_database_session_manager,
        idempotency_service=MagicMock(),
        cache_manager=cache,
        publisher=MagicMock(),
        settings=settings,
    )

    product = GenericSupplierProduct(
        supplier_id="cjdropshipping",
        supplier_pid="pid-1",
        supplier_category_id="cj-tshirt",
        category_name="t-shirts",
        name="Imported T-Shirt",
        description="shirt",
        price=Decimal("12.50"),
        quantity=8,
        in_stock=True,
        images=["https://example.com/keep.jpg", "https://example.com/remove.jpg"],
        variants=[
            SupplierProductVariant(vid="v1", variant_sku="old"),
            SupplierProductVariant(vid="v2", variant_sku="removed"),
        ],
    )
    invalid = product.model_copy(
        update={"supplier_pid": "pid-invalid", "price": Decimal("0")}
    )
    first_event = SupplierProductsFetchedEvent(
        supplier_id="cjdropshipping",
        fetch_id=uuid4(),
        batch_number=1,
        total_batches=1,
        products=[product, invalid],
    )
    first_message = first_event.model_dump(mode="json")

    try:
        await consumer.handle_supplier_products_fetched(first_message)
        await consumer.handle_supplier_products_fetched(first_message)

        async with test_database_session_manager.transaction() as session:
            imported = (
                await session.execute(
                    select(Product)
                    .where(Product.supplier_id == "cjdropshipping", Product.pid == "pid-1")
                    .options(selectinload(Product.variants), selectinload(Product.images))
                )
            ).scalar_one()
            first_variant_ids = {variant.vid: variant.id for variant in imported.variants}
            first_image_ids = {image.image_url: image.id for image in imported.images}
            assert len((await session.execute(select(SupplierImportBatch))).scalars().all()) == 1
            inbox = (await session.execute(select(SupplierImportBatch))).scalar_one()
            assert (inbox.imported, inbox.updated, inbox.failed) == (1, 0, 1)
            assert len((await session.execute(select(OutboxEvent))).scalars().all()) == 1

        updated_product = product.model_copy(
            update={
                "name": "Updated T-Shirt",
                "images": ["https://example.com/keep.jpg", "https://example.com/new.jpg"],
                "variants": [SupplierProductVariant(vid="v1", variant_sku="updated")],
            }
        )
        second_event = SupplierProductsFetchedEvent(
            supplier_id="cjdropshipping",
            fetch_id=first_event.fetch_id,
            batch_number=1,
            total_batches=1,
            products=[updated_product],
        )
        await consumer.handle_supplier_products_fetched(second_event.model_dump(mode="json"))

        async with test_database_session_manager.transaction() as session:
            imported = (
                await session.execute(
                    select(Product)
                    .where(Product.supplier_id == "cjdropshipping", Product.pid == "pid-1")
                    .options(selectinload(Product.variants), selectinload(Product.images))
                )
            ).scalar_one()
            variants = {variant.vid: variant for variant in imported.variants}
            images = {image.image_url: image for image in imported.images}
            assert variants["v1"].id == first_variant_ids["v1"]
            assert variants["v1"].variant_sku == "updated"
            assert variants["v2"].id == first_variant_ids["v2"]
            assert variants["v2"].active is False
            assert images["https://example.com/keep.jpg"].id == first_image_ids["https://example.com/keep.jpg"]
            assert "https://example.com/remove.jpg" not in images
            assert "https://example.com/new.jpg" in images
    finally:
        await test_database_session_manager.truncate_all_tables(Product.metadata)
