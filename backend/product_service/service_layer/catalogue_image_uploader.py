"""Admin-uploaded product images and category icons, into the catalogue store."""

import hashlib
from collections.abc import Callable
from uuid import uuid4

from fastapi import UploadFile

from exceptions.product_image_exceptions import ProductImageProcessingError
from storage.image_sniffer import ImageSniffer
from storage.object_store import ObjectStore, ObjectWrite


class CatalogueImageUploader:
    """
    Stores an upload under a fresh key and returns that key.

    The key, not a URL, is what the database keeps (``CatalogueImageUrl``
    adds the public origin on the way out). Keys are never reused, so the
    objects are served as immutable.
    """

    PRODUCT_PREFIX = "catalogue/uploads/products"
    CATEGORY_PREFIX = "catalogue/uploads/categories"
    CACHE_CONTROL = "public, max-age=31536000, immutable"

    def __init__(self, store: Callable[[], ObjectStore], max_bytes: int) -> None:
        # A factory, resolved on the first upload: every product route builds
        # an uploader, and a read must not fail over storage it never touches.
        self._store_factory = store
        self._max_bytes = max_bytes

    async def save_product_image(self, upload: UploadFile) -> str:
        return await self._save(upload, self.PRODUCT_PREFIX)

    async def save_product_images(self, uploads: list[UploadFile]) -> list[str]:
        return [await self.save_product_image(upload) for upload in uploads]

    async def save_category_icon(self, upload: UploadFile) -> str:
        return await self._save(upload, self.CATEGORY_PREFIX)

    async def _save(self, upload: UploadFile, prefix: str) -> str:
        # One byte over the limit is enough to know it is too large, without
        # reading an arbitrarily large body into memory.
        content = await upload.read(self._max_bytes + 1)
        await upload.seek(0)
        if len(content) > self._max_bytes:
            raise ProductImageProcessingError(
                f"Image {upload.filename!r} is larger than {self._max_bytes} bytes"
            )
        sniffed = ImageSniffer.sniff(content)
        if sniffed is None:
            raise ProductImageProcessingError(
                f"Image {upload.filename!r} is not a JPEG, PNG or WebP file"
            )
        key = f"{prefix}/{uuid4().hex}.{sniffed.extension}"
        await self._store_factory().put(
            ObjectWrite(
                key=key,
                body=content,
                content_type=sniffed.content_type,
                cache_control=self.CACHE_CONTROL,
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
        return key
