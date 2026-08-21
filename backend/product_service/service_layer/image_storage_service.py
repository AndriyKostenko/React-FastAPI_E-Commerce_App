import base64
import hashlib
import io
import os
from asyncio import to_thread
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import Logger
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import aiofiles
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, UnidentifiedImageError

from exceptions.image_generation_exceptions import ImageGenerationProviderError
from shared.contracts.artwork import GeneratedArtworkAsset, sign_artwork_asset
from shared.settings import Settings


@dataclass(frozen=True, slots=True)
class StoredImage:
    """A browser preview plus an immutable production asset manifest."""

    image_url: str
    asset: GeneratedArtworkAsset


class ImageStorageService:
    """Validate, normalize, measure, and durably store generated artwork."""

    _ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}

    def __init__(
        self,
        logger: Logger,
        settings: Settings,
        s3_client: Any | None = None,
    ) -> None:
        self._logger = logger
        self._settings = settings
        self._backend = settings.ARTWORK_STORAGE_BACKEND
        self._bucket = settings.AWS_S3_ARTWORK_BUCKET
        self._s3 = s3_client

        if self._backend == "s3":
            if not self._bucket:
                raise ValueError(
                    "AWS_S3_ARTWORK_BUCKET is required when ARTWORK_STORAGE_BACKEND=s3"
                )
            if self._s3 is None:
                # The default credential chain uses workload roles in AWS and
                # local profiles during development. Static keys never enter
                # application configuration.
                self._s3 = boto3.client(
                    "s3",
                    region_name=settings.AWS_S3_REGION,
                    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                )

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

            if self._backend == "s3":
                image_url = await self._save_to_s3(png_bytes, asset)
            else:
                image_url = await self._save_locally(png_bytes, asset.key)

            return StoredImage(image_url=image_url, asset=asset)
        except ImageGenerationProviderError:
            raise
        except (BotoCoreError, ClientError, OSError, ValueError) as error:
            self._logger.error("Failed to persist generated artwork: %s", error)
            raise ImageGenerationProviderError(
                "Failed to persist generated artwork"
            ) from error

    def _prepare_print_image(self, b64_image: str) -> tuple[bytes, int, int]:
        payload = b64_image.strip()
        if payload.startswith("data:"):
            header, separator, payload = payload.partition(",")
            if (
                not separator
                or ";base64" not in header.lower()
                or not header.lower().startswith("data:image/")
            ):
                raise ImageGenerationProviderError("Invalid image data URL")

        max_encoded_size = (self._settings.PRINT_IMAGE_MAX_BYTES * 4 // 3) + 4
        if not payload or len(payload) > max_encoded_size:
            raise ImageGenerationProviderError("Generated image payload is too large")

        try:
            source_bytes = base64.b64decode(payload, validate=True)
        except ValueError as error:
            raise ImageGenerationProviderError(
                "Generated image payload is not valid base64"
            ) from error

        if not source_bytes or len(source_bytes) > self._settings.PRINT_IMAGE_MAX_BYTES:
            raise ImageGenerationProviderError("Generated image payload is too large")

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
            save_options: dict[str, Any] = {
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

    async def _save_locally(self, image_bytes: bytes, key: str) -> str:
        media_root = Path(self._settings.MEDIA_ROOT)
        output_file = media_root / key
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = output_file.with_suffix(".tmp")
        try:
            async with aiofiles.open(temporary_file, "wb") as file:
                await file.write(image_bytes)
                await file.flush()
            os.replace(temporary_file, output_file)
        finally:
            temporary_file.unlink(missing_ok=True)
        return f"/media/{key}"

    async def _save_to_s3(
        self, image_bytes: bytes, asset: GeneratedArtworkAsset
    ) -> str:
        assert self._s3 is not None
        assert self._bucket is not None

        digest_b64 = base64.b64encode(bytes.fromhex(asset.sha256)).decode("ascii")
        request: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": asset.key,
            "Body": image_bytes,
            "ContentType": "image/png",
            "ContentDisposition": "inline",
            "CacheControl": "private, max-age=3600",
            "ChecksumSHA256": digest_b64,
            "Metadata": {
                "width-px": str(asset.width_px),
                "height-px": str(asset.height_px),
                "embedded-dpi": str(asset.embedded_dpi),
                "sha256": asset.sha256,
            },
        }
        if self._settings.AWS_S3_KMS_KEY_ID:
            request.update(
                {
                    "ServerSideEncryption": "aws:kms",
                    "SSEKMSKeyId": self._settings.AWS_S3_KMS_KEY_ID,
                }
            )
        else:
            request["ServerSideEncryption"] = "AES256"

        await to_thread(self._s3.put_object, **request)

        public_base = self._settings.AWS_S3_PUBLIC_BASE_URL
        if public_base:
            return f"{public_base.rstrip('/')}/{quote(asset.key, safe='/')}"
        return await to_thread(
            self._s3.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": asset.key},
            ExpiresIn=self._settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS,
        )
