import hashlib
import io
from asyncio import to_thread
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import Logger
from urllib.parse import quote
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from exceptions.image_generation_exceptions import ImageGenerationProviderError
from service_layer.image_payload import decode_image_payload
from shared.contracts.artwork import GeneratedArtworkAsset, sign_artwork_asset
from shared.settings import Settings
from storage.object_store import ObjectStorageError, ObjectStore, ObjectWrite


@dataclass(frozen=True, slots=True)
class StoredImage:
    """A browser preview plus an immutable production asset manifest."""

    image_url: str
    asset: GeneratedArtworkAsset


class ImageStorageService:
    """Validate, normalize, measure, and durably store generated artwork."""

    _ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}

    def __init__(self, logger: Logger, settings: Settings, store: ObjectStore) -> None:
        """``store`` is the private store: designs are never publicly listed."""
        self._logger = logger
        self._settings = settings
        self._store = store

    async def save(self, b64_image: str) -> StoredImage:
        """Persist a provider image only after print-readiness validation."""

        try:
            png_bytes, width, height = await to_thread(
                self._prepare_print_image, b64_image
            )
            now = datetime.now(UTC)
            key = f"generated-designs/{now:%Y}/{now:%m}/{uuid4().hex}.png"
            sha256 = hashlib.sha256(png_bytes).hexdigest()
            unsigned_asset = GeneratedArtworkAsset(
                key=key,
                width_px=width,
                height_px=height,
                embedded_dpi=self._settings.PRINT_IMAGE_EMBEDDED_DPI,
                sha256=sha256,
                token="0" * 43,
            )
            asset = unsigned_asset.model_copy(
                update={
                    "token": sign_artwork_asset(
                        unsigned_asset, self._settings.ARTWORK_SIGNING_KEY
                    )
                }
            )

            await self._store.put(
                ObjectWrite(
                    key=asset.key,
                    body=png_bytes,
                    content_type="image/png",
                    cache_control="private, max-age=3600",
                    content_disposition="inline",
                    metadata={
                        "width-px": str(asset.width_px),
                        "height-px": str(asset.height_px),
                        "embedded-dpi": str(asset.embedded_dpi),
                        "sha256": asset.sha256,
                    },
                    sha256=asset.sha256,
                )
            )
            return StoredImage(image_url=await self._preview_url(asset.key), asset=asset)
        except ImageGenerationProviderError:
            raise
        except (ObjectStorageError, ValueError) as error:
            self._logger.error("Failed to persist generated artwork: %s", error)
            raise ImageGenerationProviderError(
                "Failed to persist generated artwork"
            ) from error

    def _prepare_print_image(self, b64_image: str) -> tuple[bytes, int, int]:
        source_bytes = decode_image_payload(b64_image, self._settings.PRINT_IMAGE_MAX_BYTES)

        try:
            with Image.open(io.BytesIO(source_bytes)) as source:
                if source.format not in self._ALLOWED_FORMATS:
                    raise ImageGenerationProviderError(
                        "Generated artwork must be PNG, JPEG, or WebP"
                    )
                source.load()
                width, height = source.size
                self._validate_dimensions(width, height)
                icc_profile = source.info.get("icc_profile")
                normalized = source.convert("RGBA")

            output = io.BytesIO()
            save_options: dict[str, str | int | bytes | tuple[int, int]] = {
                "format": "PNG",
                "compress_level": 6,
                "dpi": (
                    self._settings.PRINT_IMAGE_EMBEDDED_DPI,
                    self._settings.PRINT_IMAGE_EMBEDDED_DPI,
                ),
            }
            if icc_profile:
                save_options["icc_profile"] = icc_profile
            normalized.save(output, **save_options)
            png_bytes = output.getvalue()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
            raise ImageGenerationProviderError(
                "Generated image is invalid or corrupted"
            ) from error

        if len(png_bytes) > self._settings.PRINT_IMAGE_MAX_BYTES:
            raise ImageGenerationProviderError(
                "Print-ready PNG exceeds the configured size limit"
            )
        return png_bytes, width, height

    def _validate_dimensions(self, width: int, height: int) -> None:
        if (
            width < self._settings.PRINT_IMAGE_MIN_WIDTH_PX
            or height < self._settings.PRINT_IMAGE_MIN_HEIGHT_PX
        ):
            raise ImageGenerationProviderError(
                "Generated artwork is too small for garment printing "
                f"({width}x{height}px; minimum "
                f"{self._settings.PRINT_IMAGE_MIN_WIDTH_PX}x"
                f"{self._settings.PRINT_IMAGE_MIN_HEIGHT_PX}px)"
            )
        if max(width, height) > self._settings.PRINT_IMAGE_MAX_DIMENSION_PX:
            raise ImageGenerationProviderError(
                "Generated artwork exceeds the maximum image dimension"
            )
        if width * height > self._settings.PRINT_IMAGE_MAX_PIXELS:
            raise ImageGenerationProviderError(
                "Generated artwork exceeds the maximum pixel count"
            )

    async def _preview_url(self, key: str) -> str:
        """Where the browser previews the design: the private CDN when one is
        configured, otherwise a presigned GET (or /media under ``local``)."""
        cdn = self._settings.AWS_S3_PUBLIC_BASE_URL
        if cdn and self._settings.OBJECT_STORAGE_BACKEND == "s3":
            return f"{cdn.rstrip('/')}/{quote(key, safe='/')}"
        return await self._store.presign_get(key, self._settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS)
