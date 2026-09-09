"""Serves and retains the print-ready artwork objects this service owns."""

from asyncio import to_thread
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import Logger
from pathlib import Path
from typing import Any
from uuid import UUID

import boto3

from database_layer.retained_artwork_repository import RetainedArtworkRepository
from exceptions.image_generation_exceptions import ImageGenerationProviderError
from models.retained_artwork_models import RetainedArtwork
from shared.contracts.artwork import GeneratedArtworkAsset, verify_artwork_asset
from shared.settings import Settings


class ArtworkManifestRejectedError(ImageGenerationProviderError):
    """The presented manifest was not issued by this service."""


class ArtworkObjectMissingError(ImageGenerationProviderError):
    """The manifest is genuine but the stored object is gone."""


@dataclass(frozen=True, slots=True)
class ArtworkDownload:
    """A time-limited way for the operator to fetch one print file."""

    download_url: str
    filename: str
    sha256: str
    content_type: str
    expires_in_seconds: int


class ArtworkAssetService:
    """Hands out print files and records which orders still need them.

    The signed manifest is the only credential accepted here. It is issued by
    ``ImageStorageService`` at generation time and stored verbatim on the paid
    order, so a caller can only obtain a download for artwork that a real
    order actually references — the object key alone is never enough.
    """

    def __init__(
        self,
        logger: Logger,
        settings: Settings,
        repository: RetainedArtworkRepository | None = None,
        s3_client: Any | None = None,
    ) -> None:
        self._logger = logger
        self._settings = settings
        self._repository = repository
        self._backend = settings.ARTWORK_STORAGE_BACKEND
        self._bucket = settings.AWS_S3_ARTWORK_BUCKET
        self._s3 = s3_client

    @property
    def repository(self) -> RetainedArtworkRepository:
        if self._repository is None:
            raise RuntimeError("ArtworkAssetService was built without a repository")
        return self._repository

    async def build_download(self, asset: GeneratedArtworkAsset) -> ArtworkDownload:
        """Resolve a manifest into a URL the operator's browser can fetch."""
        if not verify_artwork_asset(asset, self._settings.ARTWORK_SIGNING_KEY):
            raise ArtworkManifestRejectedError(
                "Artwork manifest is invalid or was not issued by this service"
            )

        filename = Path(asset.key).name
        if self._backend == "s3":
            url = await self._presign(asset.key, filename)
            expires_in = self._settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS
        else:
            url = self._local_url(asset.key)
            # A locally served file is reachable for as long as it exists;
            # report the same TTL so callers can cache uniformly.
            expires_in = self._settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS

        return ArtworkDownload(
            download_url=url,
            filename=filename,
            sha256=asset.sha256,
            content_type="image/png",
            expires_in_seconds=expires_in,
        )

    def _local_url(self, key: str) -> str:
        stored_file = Path(self._settings.MEDIA_ROOT) / key
        if not stored_file.is_file():
            raise ArtworkObjectMissingError(
                "The stored print file for this artwork no longer exists"
            )
        # Relative on purpose: the browser reaches media through the API
        # gateway origin, not product-service directly.
        return f"/media/{key}"

    async def _presign(self, key: str, filename: str) -> str:
        client = self._s3_client()
        return await to_thread(
            client.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
                "ResponseContentType": "image/png",
            },
            ExpiresIn=self._settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS,
        )

    def _s3_client(self) -> Any:
        if self._s3 is None:
            if not self._bucket:
                raise RuntimeError(
                    "AWS_S3_ARTWORK_BUCKET is required when ARTWORK_STORAGE_BACKEND=s3"
                )
            self._s3 = boto3.client(
                "s3",
                region_name=self._settings.AWS_S3_REGION,
                endpoint_url=self._settings.AWS_S3_ENDPOINT_URL,
            )
        return self._s3

    async def retain(self, order_id: UUID, artwork_keys: list[str]) -> int:
        """Protect an order's print files from the unreferenced-draft cleanup."""
        retained = 0
        for key in dict.fromkeys(artwork_keys):
            if await self.repository.get_active(order_id, key):
                continue
            await self.repository.create(
                RetainedArtwork(order_id=order_id, artwork_key=key)
            )
            retained += 1
        if retained:
            self._logger.info(
                "Retained %d artwork objects for order %s", retained, order_id
            )
        return retained

    async def release(self, order_id: UUID, reason: str = "") -> int:
        """Drop an order's holds once it can no longer need the print files."""
        holds = await self.repository.get_active_by_order(order_id)
        for hold in holds:
            hold.released_at = datetime.now(UTC)
            hold.release_reason = reason[:500] or None
            await self.repository.update(hold)
        if holds:
            self._logger.info(
                "Released %d artwork holds for order %s", len(holds), order_id
            )
        return len(holds)
