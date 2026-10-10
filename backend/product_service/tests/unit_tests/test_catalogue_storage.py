import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from PIL import Image

from exceptions.product_image_exceptions import ProductImageProcessingError
from models.catalogue_image_mirror_models import CatalogueImageMirror, MirrorStatus
from service_layer.catalogue_image_fetcher import CJ_IMAGE_SOURCES
from service_layer.catalogue_image_mirror_service import CatalogueImageMirrorService, MirrorRetryPolicy
from service_layer.catalogue_image_uploader import CatalogueImageUploader
from storage.catalogue_url import CatalogueUrlResolver
from storage.object_store import LocalObjectStore, ObjectMissingError, ObjectStorageError, ObjectWrite


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "green").save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload(content: bytes, name: str = "photo.jpg") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=name)


# ── CatalogueUrlResolver ─────────────────────────────────────────────────────

class TestCatalogueUrlResolver:
    resolver = CatalogueUrlResolver("https://cdn.example.com/catalogue/")

    def test_a_key_gets_the_public_origin(self) -> None:
        assert self.resolver.resolve("catalogue/cj/ab/abc.jpg") == "https://cdn.example.com/catalogue/catalogue/cj/ab/abc.jpg"

    def test_a_key_is_url_quoted(self) -> None:
        assert self.resolver.resolve("catalogue/uploads/a b.jpg").endswith("/catalogue/uploads/a%20b.jpg")

    @pytest.mark.parametrize("value", [
        "https://oss-cf.cjdropshipping.com/product/a.jpg",  # a CJ image not yet copied
        "http://127.0.0.1:8333/x.jpg",
        "/media/generated-designs/a.png",                   # an old local path
        "",
    ])
    def test_a_loadable_value_passes_through(self, value: str) -> None:
        assert self.resolver.resolve(value) == value

    def test_resolving_twice_changes_nothing(self) -> None:
        once = self.resolver.resolve("catalogue/cj/ab/abc.jpg")
        assert self.resolver.resolve(once) == once

    def test_the_local_backend_serves_keys_under_media(self) -> None:
        resolver = CatalogueUrlResolver.from_settings(SimpleNamespace(OBJECT_STORAGE_BACKEND="local"))
        assert resolver.resolve("catalogue/cj/a.jpg") == "/media/catalogue/cj/a.jpg"

    def test_s3_without_a_public_origin_is_refused_by_name(self) -> None:
        settings = SimpleNamespace(OBJECT_STORAGE_BACKEND="s3", AWS_S3_CATALOGUE_PUBLIC_BASE_URL=None)
        with pytest.raises(RuntimeError, match="AWS_S3_CATALOGUE_PUBLIC_BASE_URL"):
            CatalogueUrlResolver.from_settings(settings)


# ── Where supplier images may come from ───────────────────────────────────────

class TestCjImageSources:
    @pytest.mark.parametrize("url", [
        "https://cf.cjdropshipping.com/a.jpg",
        "https://oss-cf.cjdropshipping.com/product/2025/a.jpg",
    ])
    def test_cj_cdn_over_https_is_allowed(self, url: str) -> None:
        assert CJ_IMAGE_SOURCES.allows(url)

    @pytest.mark.parametrize("url", [
        "http://cf.cjdropshipping.com/a.jpg",        # not HTTPS
        "https://evilcjdropshipping.com/a.jpg",      # not a subdomain
        "https://cjdropshipping.com.evil.example/a.jpg",
        "https://169.254.169.254/latest/meta-data",  # cloud metadata
        "https://127.0.0.1/a.jpg",
        "file:///etc/passwd",
        "not a url",
    ])
    def test_anything_else_is_refused(self, url: str) -> None:
        assert not CJ_IMAGE_SOURCES.allows(url)


# ── Mirror keys and retries ───────────────────────────────────────────────────

class TestMirrorKeysAndRetries:
    def test_the_key_depends_only_on_the_source_url(self) -> None:
        url = "https://cf.cjdropshipping.com/a.jpg"
        key = CatalogueImageMirrorService.object_key(url, "jpg")
        assert key == CatalogueImageMirrorService.object_key(url, "jpg")
        assert key != CatalogueImageMirrorService.object_key(url + "?v=2", "jpg")
        assert key.startswith("catalogue/cj/") and key.endswith(".jpg")

    def test_a_new_url_is_due(self) -> None:
        assert MirrorRetryPolicy.is_due(None, datetime.now(UTC))

    def test_a_failure_waits_longer_each_time_up_to_a_day(self) -> None:
        now = datetime(2026, 10, 9, 12, tzinfo=UTC)

        def row(attempts: int, minutes_ago: float) -> CatalogueImageMirror:
            return CatalogueImageMirror(
                source_url="u", status=MirrorStatus.PENDING.value, attempts=attempts,
                last_attempt_at=now - timedelta(minutes=minutes_ago),
            )

        assert not MirrorRetryPolicy.is_due(row(1, 14), now)
        assert MirrorRetryPolicy.is_due(row(1, 15), now)
        assert not MirrorRetryPolicy.is_due(row(3, 59), now)
        assert MirrorRetryPolicy.is_due(row(3, 60), now)
        assert MirrorRetryPolicy.is_due(row(9, 24 * 60), now)


# ── Admin uploads ─────────────────────────────────────────────────────────────

class TestCatalogueImageUploader:
    async def test_an_upload_is_stored_under_a_fresh_key(self, tmp_path: Path) -> None:
        store = LocalObjectStore(tmp_path)
        uploader = CatalogueImageUploader(lambda: store, max_bytes=1_000_000)
        content = _jpeg()

        key = await uploader.save_product_image(_upload(content, "../../etc/passwd.png"))

        # The client's name and type are ignored: the key and extension come
        # from the service and the bytes.
        assert key.startswith("catalogue/uploads/products/") and key.endswith(".jpg")
        assert await store.get(key) == content
        assert key != await uploader.save_product_image(_upload(content))

    async def test_a_category_icon_has_its_own_prefix(self, tmp_path: Path) -> None:
        uploader = CatalogueImageUploader(lambda: LocalObjectStore(tmp_path), max_bytes=1_000_000)
        assert (await uploader.save_category_icon(_upload(_jpeg()))).startswith("catalogue/uploads/categories/")

    async def test_a_file_that_is_not_an_image_is_refused(self, tmp_path: Path) -> None:
        uploader = CatalogueImageUploader(lambda: LocalObjectStore(tmp_path), max_bytes=1_000_000)
        with pytest.raises(ProductImageProcessingError, match="not a JPEG, PNG or WebP"):
            await uploader.save_product_image(_upload(b"<svg onload=alert(1)>", "logo.png"))
        assert not any(tmp_path.rglob("*.*"))

    async def test_a_file_over_the_limit_is_refused(self, tmp_path: Path) -> None:
        content = _jpeg()
        uploader = CatalogueImageUploader(lambda: LocalObjectStore(tmp_path), max_bytes=len(content) - 1)
        with pytest.raises(ProductImageProcessingError, match="larger than"):
            await uploader.save_product_image(_upload(content))

    async def test_reads_never_build_the_store(self) -> None:
        def unavailable():
            raise AssertionError("the store was built without an upload")

        CatalogueImageUploader(unavailable, max_bytes=10)


# ── LocalObjectStore ──────────────────────────────────────────────────────────

class TestLocalObjectStore:
    @pytest.mark.parametrize("key", ["../outside.png", "/etc/passwd", "a/../../b.png", ""])
    async def test_a_key_cannot_leave_the_root(self, tmp_path: Path, key: str) -> None:
        store = LocalObjectStore(tmp_path / "root")
        with pytest.raises(ObjectStorageError):
            await store.put(ObjectWrite(key=key, body=b"x", content_type="image/png", cache_control="no-store"))

    async def test_a_presigned_url_for_a_missing_object_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ObjectMissingError):
            await LocalObjectStore(tmp_path).presign_get("generated-designs/none.png", 60)

    async def test_a_stored_object_is_served_under_media(self, tmp_path: Path) -> None:
        store = LocalObjectStore(tmp_path)
        await store.put(ObjectWrite(key="a/b.png", body=b"x", content_type="image/png", cache_control="no-store"))
        assert await store.presign_get("a/b.png", 60) == "/media/a/b.png"
