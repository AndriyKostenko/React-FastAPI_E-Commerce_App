import base64
import os
from logging import Logger
from pathlib import Path
from uuid import uuid4

import aiofiles

from exceptions.image_generation_exceptions import ImageGenerationProviderError


class ImageStorageService:
    """Decodes base64 image data and persists it to the media directory."""

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    async def save(self, b64_image: str) -> str:
        """
        Decode a base64-encoded image (plain or data-URL) and write it to disk.

        Returns:
            The public URL path, e.g. ``/media/generated/<uuid>.png``.
        Raises:
            ImageGenerationProviderError: on decode or I/O failure.
        """
        try:
            media_root = Path(os.environ.get("MEDIA_ROOT", "/media"))
            generated_dir = media_root / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{uuid4().hex}.png"
            output_file = generated_dir / filename
            image_payload = b64_image.strip()

            if image_payload.startswith("data:"):
                _, separator, image_payload = image_payload.partition(",")
                if not separator or not image_payload:
                    raise ValueError("Invalid image data URL")

            image_bytes = base64.b64decode(image_payload, validate=True)

            async with aiofiles.open(output_file, "wb") as file:
                await file.write(image_bytes)

            return f"/media/generated/{filename}"
        except (ValueError, OSError) as error:
            self._logger.error(f"Failed to save generated image: {error}")
            raise ImageGenerationProviderError("Failed to save generated image to disk")
