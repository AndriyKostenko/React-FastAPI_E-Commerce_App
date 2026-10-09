"""Serves and retains the print-ready artwork objects this service owns."""

from dataclasses import dataclass
from datetime import UTC, datetime
from logging import Logger
from pathlib import Path
from uuid import UUID

from database_layer.retained_artwork_repository import RetainedArtworkRepository
from exceptions.image_generation_exceptions import ImageGenerationProviderError
from models.retained_artwork_models import RetainedArtwork
from shared.contracts.artwork import GeneratedArtworkAsset, verify_artwork_asset
from shared.settings import Settings
from storage.object_store import ObjectMissingError, ObjectStore


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
        store: ObjectStore | None = None,
    ) -> None:
        self._logger = logger
        self._settings = settings
        self._repository = repository
        # The private store; only build_download needs it, so the event
        # consumer (retain/release only) is built without one.
        self._store = store

    @property
    def repository(self) -> RetainedArtworkRepository:
        if self._repository is None:
            raise RuntimeError("ArtworkAssetService was built without a repository")
        return self._repository

    @property
    def store(self) -> ObjectStore:
        if self._store is None:
            raise RuntimeError("ArtworkAssetService was built without an object store")
        return self._store

    async def build_download(self, asset: GeneratedArtworkAsset) -> ArtworkDownload:
        """Resolve a manifest into a URL the operator's browser can fetch."""
        if not verify_artwork_asset(asset, self._settings.ARTWORK_SIGNING_KEY):
            raise ArtworkManifestRejectedError(
                "Artwork manifest is invalid or was not issued by this service"
            )

        filename = Path(asset.key).name
        ttl = self._settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS
        try:
            # A presigned GET under s3 (an attachment, so the browser saves
            # it); a /media path under local, reachable for as long as the file
            # exists -- the same TTL is reported so callers can cache uniformly.
            url = await self.store.presign_get(
                asset.key, ttl, download_filename=filename, content_type="image/png"
            )
        except ObjectMissingError as error:
            raise ArtworkObjectMissingError(
                "The stored print file for this artwork no longer exists"
            ) from error

        return ArtworkDownload(
            download_url=url,
            filename=filename,
            sha256=asset.sha256,
            content_type="image/png",
            expires_in_seconds=ttl,
        )

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
