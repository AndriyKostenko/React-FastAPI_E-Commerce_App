"""
Copying supplier images into the catalogue store, end to end: products come
in through the real supplier-import consumer, a local HTTP server stands in
for CJ's CDN, the copies go to the real local S3 server (test bucket) and the
rows are read back from the real test database.
"""

import io
from collections.abc import AsyncIterator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from aiohttp import ClientSession, web
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from event_consumer.product_event_consumer import ProductEventConsumer
from models.catalogue_image_mirror_models import CatalogueImageMirror, MirrorStatus
from models.product_models import Product
from resources import settings
from service_layer.catalogue_image_fetcher import (
    CJ_IMAGE_SOURCES,
    CatalogueImageFetcher,
    ImageSourcePolicy,
)
from service_layer.catalogue_image_mirror_service import CatalogueImageMirrorService
from shared.contracts.events import SupplierProductsFetchedEvent
from shared.contracts.supplier import GenericSupplierProduct, SupplierProductVariant
from storage.catalogue_url import CatalogueUrlResolver
from storage.object_storage_provider import ObjectStorageProvider
from tests.integration_tests.test_object_storage_s3 import _http_get

# The fixtures (database, CDN stand-in, HTTP session) run on the session's
# event loop; aiohttp needs the tests on that same loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")

LOCAL_SOURCES = ImageSourcePolicy(schemes=("http",), hosts=("127.0.0.1",))


def _image(fmt: str, colour: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), colour).save(buffer, format=fmt)
    return buffer.getvalue()


JPEG = _image("JPEG", "red")
PNG = _image("PNG", "blue")


@pytest.fixture
async def cdn() -> AsyncIterator[str]:
    """A stand-in for CJ's CDN on a free local port."""
    routes = {
        "/main.jpg": web.Response(body=JPEG, content_type="image/jpeg"),
        "/gallery.jpg": web.Response(body=JPEG, content_type="image/jpeg"),
        "/variant.png": web.Response(body=PNG, content_type="image/png"),
        "/error-page.jpg": web.Response(text="<html>busy</html>", content_type="text/html"),
    }

    async def serve(request: web.Request) -> web.StreamResponse:
        return routes.get(request.path) or web.Response(status=404)

    app = web.Application()
    app.router.add_get("/{name}", serve)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


@pytest.fixture
async def db(test_database_session_manager):
    await test_database_session_manager.truncate_all_tables(Product.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Product.metadata)


@pytest.fixture
async def http() -> AsyncIterator[ClientSession]:
    async with ClientSession() as session:
        yield session


def _cache() -> MagicMock:
    cache = MagicMock()
    cache.invalidate_namespace = AsyncMock()
    return cache


def _mirror(db, http: ClientSession, sources: ImageSourcePolicy = LOCAL_SOURCES) -> CatalogueImageMirrorService:
    return CatalogueImageMirrorService(
        database=db,
        store=ObjectStorageProvider(settings).catalogue(),
        fetcher=CatalogueImageFetcher(http, max_bytes=1_000_000, sources=sources),
        cache_manager=_cache(),
        settings=settings,
        logger=MagicMock(),
    )


async def _import(db, pid: str, main: str, gallery: list[str], variant_image: str | None) -> None:
    product = GenericSupplierProduct(
        supplier_id="cjdropshipping", supplier_pid=pid, supplier_category_id="cj-tshirt",
        category_name="t-shirts", name=f"Tee {pid}", description="shirt", price=Decimal("12.50"),
        quantity=12, in_stock=True, image_url=main, images=gallery,
        variants=[SupplierProductVariant(vid=f"{pid}-S", variant_sku="S", inventory_num=7, variant_image=variant_image)],
    )
    consumer = ProductEventConsumer(
        logger=MagicMock(), database=db, idempotency_service=MagicMock(),
        cache_manager=_cache(), publisher=MagicMock(), settings=settings,
    )
    await consumer.handle_supplier_products_fetched(SupplierProductsFetchedEvent(
        supplier_id="cjdropshipping", fetch_id=uuid4(), batch_number=1, total_batches=1, products=[product],
    ).model_dump(mode="json"))


async def _product(db, pid: str) -> Product:
    async with db.transaction() as session:
        return (await session.execute(
            select(Product).where(Product.pid == pid)
            .options(selectinload(Product.images), selectinload(Product.variants))
        )).scalar_one()


async def _mirror_row(db, url: str) -> CatalogueImageMirror:
    async with db.transaction() as session:
        return (await session.execute(
            select(CatalogueImageMirror).where(CatalogueImageMirror.source_url == url)
        )).scalar_one()


async def test_every_supplier_url_is_replaced_by_a_public_copy(db, http, cdn) -> None:
    await _import(db, "p1", f"{cdn}/main.jpg", [f"{cdn}/main.jpg", f"{cdn}/gallery.jpg"], f"{cdn}/variant.png")

    report = await _mirror(db, http).mirror_pending()

    assert report.mirrored == 3 and report.failed == 0
    product = await _product(db, "p1")
    keys = [product.image_url, *(i.image_url for i in product.images), product.variants[0].variant_image]
    assert all(key.startswith("catalogue/cj/") for key in keys)
    # One object for the URL used as both main and gallery image.
    assert product.image_url in {i.image_url for i in product.images}
    resolver = CatalogueUrlResolver.from_settings(settings)
    status, body, headers = _http_get(resolver.resolve(product.image_url))
    assert status == 200 and body == JPEG
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"
    status, body, _ = _http_get(resolver.resolve(product.variants[0].variant_image))
    assert status == 200 and body == PNG


async def test_the_next_supplier_sync_keeps_the_copies(db, http, cdn) -> None:
    urls = (f"{cdn}/main.jpg", [f"{cdn}/gallery.jpg"], f"{cdn}/variant.png")
    await _import(db, "p2", *urls)
    await _mirror(db, http).mirror_pending()
    before = await _product(db, "p2")

    # CJ keeps sending its own URLs; the rows must not go back to them.
    await _import(db, "p2", *urls)

    after = await _product(db, "p2")
    assert after.image_url == before.image_url
    assert {i.image_url for i in after.images} == {i.image_url for i in before.images}
    assert {i.id for i in after.images} == {i.id for i in before.images}
    assert after.variants[0].variant_image == before.variants[0].variant_image
    assert (await _mirror(db, http).mirror_pending()).attempted == 0


async def test_an_image_that_cannot_be_copied_stays_on_the_supplier(db, http, cdn) -> None:
    missing, error_page = f"{cdn}/gone.jpg", f"{cdn}/error-page.jpg"
    await _import(db, "p3", missing, [error_page], None)

    report = await _mirror(db, http).mirror_pending()

    assert report.failed == 2 and report.mirrored == 0
    product = await _product(db, "p3")
    assert product.image_url == missing
    assert [i.image_url for i in product.images] == [error_page]
    for url in (missing, error_page):
        row = await _mirror_row(db, url)
        assert row.status == MirrorStatus.PENDING and row.attempts == 1 and row.last_error
    # Not due again yet: the retry waits.
    assert (await _mirror(db, http).mirror_pending()).attempted == 0


async def test_a_url_outside_the_supplier_cdn_is_never_fetched(db, http, cdn) -> None:
    # The production policy: HTTPS on CJ's domain only. The local stand-in is
    # neither, so it must be refused without a request and given up on.
    await _import(db, "p4", f"{cdn}/main.jpg", [], None)

    report = await _mirror(db, http, sources=CJ_IMAGE_SOURCES).mirror_pending()

    assert report.given_up == 1 and report.mirrored == 0
    row = await _mirror_row(db, f"{cdn}/main.jpg")
    assert row.status == MirrorStatus.FAILED and "Not a supplier CDN URL" in (row.last_error or "")
    assert (await _product(db, "p4")).image_url == f"{cdn}/main.jpg"
