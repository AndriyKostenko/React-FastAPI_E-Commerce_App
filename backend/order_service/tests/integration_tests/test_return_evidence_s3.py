"""
Return photos in the real local S3 server (SeaweedFS), with order-service's
own key, on the private test bucket ``dev.sh test`` selects.
"""

from uuid import uuid4

import pytest

from service_layer.return_evidence_storage import (
    EvidencePhoto,
    ReturnEvidenceStorageError,
    S3ReturnEvidenceStorage,
)
from shared.settings import get_settings

PHOTO = EvidencePhoto(content=b"\xff\xd8\xff\xe0" + b"\x00" * 64, content_type="image/jpeg", extension="jpg")


@pytest.fixture(scope="module")
def storage() -> S3ReturnEvidenceStorage:
    settings = get_settings()
    assert settings.OBJECT_STORAGE_BACKEND == "s3", "run through ./local/dev.sh test order_service"
    assert settings.AWS_S3_PRIVATE_BUCKET and settings.AWS_S3_PRIVATE_BUCKET.endswith("-test")
    return S3ReturnEvidenceStorage(settings)


async def test_a_photo_round_trips(storage: S3ReturnEvidenceStorage) -> None:
    key = f"{uuid4()}/{uuid4()}/0.jpg"
    await storage.save(key, PHOTO)
    assert await storage.load(key) == PHOTO.content


async def test_a_missing_photo_reads_as_none(storage: S3ReturnEvidenceStorage) -> None:
    assert await storage.load(f"{uuid4()}/{uuid4()}/0.jpg") is None


@pytest.mark.parametrize("key", ["../generated-designs/x.png", "/etc/passwd", ""])
async def test_a_key_cannot_leave_the_evidence_prefix(storage: S3ReturnEvidenceStorage, key: str) -> None:
    with pytest.raises(ValueError):
        await storage.save(key, PHOTO)


async def test_order_service_cannot_read_generated_designs(storage: S3ReturnEvidenceStorage) -> None:
    # Bypass the prefix on purpose: the bucket's own rules must refuse it too.
    client, bucket = storage._client, get_settings().AWS_S3_PRIVATE_BUCKET
    with pytest.raises(Exception, match="AccessDenied"):
        client.get_object(Bucket=bucket, Key=f"generated-designs/{uuid4().hex}.png")


async def test_a_storage_failure_is_reported_as_such(storage: S3ReturnEvidenceStorage) -> None:
    broken = S3ReturnEvidenceStorage(get_settings(), client=storage._client)
    broken._bucket = "no-such-bucket-for-order-service"
    with pytest.raises(ReturnEvidenceStorageError):
        await broken.save(f"{uuid4()}/{uuid4()}/0.jpg", PHOTO)
