"""
The photo check between a CJ batch and the store, through the real import
consumer and the real product test database. Only the model's verdict is
scripted (tests/image_review_fakes.py).

Rules: a new product is created only when its main photo is approved, and
then with the model's description; a verdict is stored per photo and reused,
so an approved product keeps that description on later syncs and a rejected
photo is never paid for twice; with no answer nothing is stored and the next
sync asks again; a reviewed product whose new photo is rejected is left as it
is. The one-off run reviews what was imported before, and only reports
rejected products.
"""

from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from contracts.events import SupplierProductsFetchedEvent
from contracts.supplier import GenericSupplierProduct, SupplierProductVariant
from event_consumer.product_event_consumer import ProductEventConsumer
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.catalogue_image_mirror_models import CatalogueImageMirror, MirrorStatus
from models.product_models import Product
from models.supplier_image_review_models import SupplierImageReview
from models.supplier_import_models import SupplierImportBatch
from resources import settings
from service_layer.image_review import ImageReviewUnavailableError
from tests.image_review_fakes import APPROVED_DESCRIPTION, ScriptedReviewer, approved, rejected, review_service

PHOTO = "https://cf.cjdropshipping.com/tee-front.jpg"
CHART = "https://cf.cjdropshipping.com/size-chart.jpg"


def _product(pid: str = "pid-1", photo: str | None = PHOTO, **changes) -> GenericSupplierProduct:
    product = GenericSupplierProduct(
        supplier_id="cjdropshipping", supplier_pid=pid, supplier_category_id="cj-tshirt",
        category_name="t-shirts", name=f"tee {pid}", description="CJ's own text", price=Decimal("12.50"),
        quantity=8, in_stock=True, image_url=photo, images=[photo] if photo else [],
        variants=[SupplierProductVariant(vid=f"{pid}-v1", variant_sku="S")],
    )
    return product.model_copy(update=changes)


class _Store:
    """The import consumer and the rows it writes."""

    def __init__(self, db: TestDatabaseSessionManager, reviewer: ScriptedReviewer) -> None:
        self.db = db
        self.reviewer = reviewer
        cache = MagicMock()
        cache.invalidate_namespace = AsyncMock()
        self.consumer = ProductEventConsumer(
            logger=MagicMock(), database=db, idempotency_service=MagicMock(), cache_manager=cache,
            publisher=MagicMock(), settings=settings, image_review=review_service(db, reviewer),
        )

    async def sync(self, *products: GenericSupplierProduct) -> dict:
        message = SupplierProductsFetchedEvent(
            supplier_id="cjdropshipping", fetch_id=uuid4(), batch_number=1, total_batches=1, products=list(products),
        ).model_dump(mode="json")
        await self.consumer.handle_supplier_products_fetched(message)
        return message

    async def product(self, pid: str = "pid-1") -> Product | None:
        async with self.db.transaction() as session:
            return (await session.execute(select(Product).where(Product.pid == pid))).scalar_one_or_none()

    async def reviews(self) -> list[SupplierImageReview]:
        async with self.db.transaction() as session:
            return list((await session.execute(select(SupplierImageReview))).scalars().all())

    async def last_report(self) -> SupplierImportBatch:
        async with self.db.transaction() as session:
            return (await session.execute(
                select(SupplierImportBatch).order_by(SupplierImportBatch.date_created.desc()).limit(1)
            )).scalar_one()

    async def forget_reviews(self) -> None:
        """As if the products had been imported before photo reviews existed."""
        async with self.db.transaction() as session:
            await session.execute(delete(SupplierImageReview))


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.truncate_all_tables(Product.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Product.metadata)


class TestNewProducts:
    async def test_an_approved_photo_brings_the_product_in_with_the_models_description(self, db) -> None:
        store = _Store(db, ScriptedReviewer())
        await store.sync(_product())
        product = await store.product()
        assert product is not None and product.description == APPROVED_DESCRIPTION
        [review] = await store.reviews()
        assert (review.pid, review.image_url, review.verdict) == ("pid-1", PHOTO, "approved")

    async def test_a_rejected_photo_keeps_the_product_out_and_says_why(self, db) -> None:
        store = _Store(db, ScriptedReviewer({CHART: rejected("Only a size chart is shown.")}))
        await store.sync(_product(photo=CHART))
        assert await store.product() is None
        report = await store.last_report()
        assert (report.imported, report.failed) == (0, 1)
        assert report.errors == ["pid-1: photo rejected: Only a size chart is shown."]
        assert [r.verdict for r in await store.reviews()] == ["rejected"]

    async def test_without_an_answer_nothing_is_stored_and_the_next_sync_asks_again(self, db) -> None:
        down = ScriptedReviewer(default=ImageReviewUnavailableError("OpenRouter answered HTTP 503"))
        await _Store(db, down).sync(_product())
        assert await _Store(db, down).product() is None
        assert await _Store(db, down).reviews() == []

        back = ScriptedReviewer()
        await _Store(db, back).sync(_product())
        assert back.asked == [PHOTO]
        assert (await _Store(db, back).product()).description == APPROVED_DESCRIPTION

    async def test_a_product_without_a_photo_is_not_imported(self, db) -> None:
        store = _Store(db, ScriptedReviewer())
        await store.sync(_product(photo=None))
        assert await store.product() is None
        assert store.reviewer.asked == []
        assert (await store.last_report()).errors == ["pid-1: no photo to review"]


class TestLaterSyncs:
    async def test_an_approved_product_keeps_its_description_without_a_second_call(self, db) -> None:
        store = _Store(db, ScriptedReviewer())
        await store.sync(_product())
        await store.sync(_product(description="CJ's rewritten text", name="tee renamed"))
        product = await store.product()
        assert product.description == APPROVED_DESCRIPTION
        assert product.name == "tee renamed"  # the rest of CJ's update still lands
        assert store.reviewer.asked == [PHOTO]

    async def test_a_rejected_photo_is_never_reviewed_twice(self, db) -> None:
        store = _Store(db, ScriptedReviewer({CHART: rejected()}))
        await store.sync(_product(photo=CHART))
        await store.sync(_product(photo=CHART))
        assert store.reviewer.asked == [CHART]

    async def test_a_redelivered_batch_asks_nothing(self, db) -> None:
        store = _Store(db, ScriptedReviewer())
        message = await store.sync(_product())
        await store.consumer.handle_supplier_products_fetched(message)
        assert store.reviewer.asked == [PHOTO]

    async def test_a_new_photo_that_is_rejected_leaves_the_product_as_it_is(self, db) -> None:
        store = _Store(db, ScriptedReviewer({CHART: rejected()}))
        await store.sync(_product())
        await store.sync(_product(photo=CHART, name="tee renamed", price=Decimal("30.00")))
        product = await store.product()
        assert (product.name, product.description) == ("tee pid-1", APPROVED_DESCRIPTION)
        assert store.reviewer.asked == [PHOTO, CHART]

    async def test_a_new_photo_that_is_approved_gets_a_new_description(self, db) -> None:
        back = "https://cf.cjdropshipping.com/tee-back.jpg"
        store = _Store(db, ScriptedReviewer({back: approved("A white tee with a small embroidered fox on the back, centred below the collar.")}))
        await store.sync(_product())
        await store.sync(_product(photo=back))
        assert (await store.product()).description.startswith("A white tee with a small embroidered fox")

    async def test_a_product_imported_before_reviews_is_updated_as_before(self, db) -> None:
        store = _Store(db, ScriptedReviewer())
        await store.sync(_product())
        await store.forget_reviews()
        await store.sync(_product(description="CJ's rewritten text"))
        assert (await store.product()).description == "CJ's rewritten text"
        assert store.reviewer.asked == [PHOTO]  # only the first import asked


class TestCatalogueRun:
    async def test_it_describes_approved_products_and_only_reports_rejected_ones(self, db) -> None:
        importer = _Store(db, ScriptedReviewer())
        await importer.sync(_product("pid-ok"), _product("pid-chart", photo=CHART))
        await importer.forget_reviews()

        reviewer = ScriptedReviewer({CHART: rejected("Only a size chart is shown.")})
        report = await review_service(db, reviewer).review_catalogue(limit=10)
        assert report.described == ["pid-ok"]
        assert report.rejected == [("pid-chart", "tee pid-chart", "Only a size chart is shown.")]
        # Never deleted; from now on syncs leave it as it is.
        assert await importer.product("pid-chart") is not None
        await _Store(db, reviewer).sync(_product("pid-chart", photo=CHART, name="tee renamed"))
        assert (await importer.product("pid-chart")).name == "tee pid-chart"

    async def test_a_copied_image_is_reviewed_at_its_supplier_url(self, db) -> None:
        importer = _Store(db, ScriptedReviewer())
        await importer.sync(_product())
        await importer.forget_reviews()
        async with db.transaction() as session:
            product = (await session.execute(select(Product).where(Product.pid == "pid-1"))).scalar_one()
            product.image_url = "catalogue/cj/tee-front.jpg"
            session.add(CatalogueImageMirror(source_url=PHOTO, status=MirrorStatus.MIRRORED.value,
                                             object_key="catalogue/cj/tee-front.jpg"))

        reviewer = ScriptedReviewer()
        await review_service(db, reviewer).review_catalogue(limit=10)
        assert reviewer.asked == [PHOTO]

    async def test_no_answer_is_reported_and_tried_again_by_the_next_run(self, db) -> None:
        importer = _Store(db, ScriptedReviewer())
        await importer.sync(_product())
        await importer.forget_reviews()

        report = await review_service(db, ScriptedReviewer(default=ImageReviewUnavailableError("timeout"))).review_catalogue(limit=10)
        assert report.unavailable == [("pid-1", "timeout")]
        assert await importer.reviews() == []
        later = await review_service(db, ScriptedReviewer()).review_catalogue(limit=10)
        assert later.described == ["pid-1"]

    async def test_the_limit_bounds_the_calls(self, db) -> None:
        importer = _Store(db, ScriptedReviewer())
        await importer.sync(*(_product(f"pid-{n}", photo=f"https://cf.cjdropshipping.com/{n}.jpg") for n in range(3)))
        await importer.forget_reviews()
        reviewer = ScriptedReviewer()
        report = await review_service(db, reviewer).review_catalogue(limit=2)
        assert len(reviewer.asked) == 2 and len(report.described) == 2
