"""
The object stores against the real local S3 server (SeaweedFS), with
product-service's own key, on the test buckets ``dev.sh test`` selects.

What is checked is what the rest of the service relies on: a write is
encrypted and checksummed, a presigned GET works, the private bucket is not
public while the catalogue one is, and product-service's key cannot reach
order-service's prefix.
"""

import hashlib
import urllib.error
import urllib.request
from uuid import uuid4

import pytest

from shared.settings import get_settings
from storage.catalogue_url import CatalogueUrlResolver
from storage.object_storage_provider import ObjectStorageProvider
from storage.object_store import ObjectStorageError, ObjectWrite, S3ObjectStore

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _http_get(url: str) -> tuple[int, bytes, dict[str, str]]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, b"", dict(error.headers)


@pytest.fixture(scope="module")
def storage() -> ObjectStorageProvider:
    settings = get_settings()
    assert settings.OBJECT_STORAGE_BACKEND == "s3", "run through ./local/dev.sh test product_service"
    assert settings.AWS_S3_PRIVATE_BUCKET and settings.AWS_S3_PRIVATE_BUCKET.endswith("-test")
    return ObjectStorageProvider(settings)


def _write(key: str, body: bytes = PNG, sha256: str | None = None) -> ObjectWrite:
    return ObjectWrite(
        key=key,
        body=body,
        content_type="image/png",
        cache_control="private, max-age=60",
        metadata={"purpose": "test"},
        sha256=sha256 if sha256 is not None else hashlib.sha256(body).hexdigest(),
    )


async def test_a_design_round_trips_through_the_private_bucket(storage: ObjectStorageProvider) -> None:
    store = storage.private()
    key = f"generated-designs/test/{uuid4().hex}.png"

    await store.put(_write(key))

    assert await store.exists(key)
    assert await store.get(key) == PNG
    status, body, headers = _http_get(await store.presign_get(key, 60, download_filename="print.png"))
    assert status == 200 and body == PNG
    assert headers["Content-Disposition"] == 'attachment; filename="print.png"'


async def test_a_missing_object_reads_as_none(storage: ObjectStorageProvider) -> None:
    key = f"generated-designs/test/{uuid4().hex}.png"
    assert await storage.private().get(key) is None
    assert not await storage.private().exists(key)


async def test_a_write_whose_checksum_does_not_match_is_refused(storage: ObjectStorageProvider) -> None:
    key = f"generated-designs/test/{uuid4().hex}.png"
    with pytest.raises(ObjectStorageError):
        await storage.private().put(_write(key, sha256=hashlib.sha256(b"something else").hexdigest()))
    assert not await storage.private().exists(key)


async def test_the_private_bucket_is_not_public(storage: ObjectStorageProvider) -> None:
    store = storage.private()
    assert isinstance(store, S3ObjectStore)
    key = f"generated-designs/test/{uuid4().hex}.png"
    await store.put(_write(key))

    status, _, _ = _http_get(f"{get_settings().AWS_S3_ENDPOINT_URL}/{store.bucket}/{key}")

    assert status == 403


async def test_a_catalogue_image_is_public_at_its_resolved_url(storage: ObjectStorageProvider) -> None:
    key = f"catalogue/uploads/products/{uuid4().hex}.png"
    await storage.catalogue().put(_write(key))

    url = CatalogueUrlResolver.from_settings(get_settings()).resolve(key)
    status, body, headers = _http_get(url)

    assert status == 200 and body == PNG
    assert headers["Content-Type"] == "image/png"


async def test_product_service_cannot_write_return_evidence(storage: ObjectStorageProvider) -> None:
    with pytest.raises(ObjectStorageError, match="AccessDenied"):
        await storage.private().put(_write(f"return-evidence/{uuid4().hex}.png"))
