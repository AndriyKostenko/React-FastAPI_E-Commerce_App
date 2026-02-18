import os
from datetime import datetime

import aiofiles
from fastapi import UploadFile

from exceptions.product_image_exceptions import ProductImageProcessingError
from shared.schemas.product_image_schema import ImageType


class ImageProcessingManager:
    BASE_DIR = os.path.dirname(__file__)
    MEDIA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../media/images"))
    ICONS_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../media/icons"))

    def __init__(self):
        pass  # Directories are created lazily when files are first saved

    def _ensure_dirs(self):
        """Create media directories only when actually needed (lazy init)."""
        os.makedirs(self.MEDIA_DIR, exist_ok=True)
        os.makedirs(self.ICONS_DIR, exist_ok=True)


    @staticmethod
    def _safe_split_filename(filename: str | None) -> tuple[str, str]:
        """
        Returns (name, extension_with_dot)
        """
        if not filename or "." not in filename:
            return "file", ""

        name, ext = filename.rsplit(".", 1)
        return name, f".{ext}"

    @staticmethod
    def _generate_filename(original_filename: str | None) -> str:
        """Generate a unique filename based on the original filename and current timestamp."""
        name, ext = ImageProcessingManager._safe_split_filename(original_filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{name}_{timestamp}{ext}"

    async def _save_file(self, file: UploadFile, target_dir: str) -> str:
        """Save an uploaded image to the specified directory and return its path."""
        self._ensure_dirs()  # create dirs only when actually saving a file
        filename = self._generate_filename(file.filename)
        file_path = os.path.join(target_dir, filename)
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)
        await file.seek(0)
        return file_path


    async def save_image(self, image: UploadFile) -> str:
        """Save a single image and return its path."""
        return await self._save_file(image, self.MEDIA_DIR)

    async def save_images(self, images: list[UploadFile]) -> list[str]:
        return [await self.save_image(image) for image in images]

    async def save_icon(self, icon: UploadFile) -> str:
        """Save a single icon and return its path."""
        return await self._save_file(icon, self.ICONS_DIR)

    def create_metadata_list(
        self,
        image_urls: list[str],
        image_colors: list[str],
        image_color_codes: list[str],
    ) -> list[ImageType]:
        """
        Create ImageType metadata objects from parallel lists.
        """
        print(
            f"image_urls: {image_urls}, image_colors: {image_colors}, image_color_codes: {image_color_codes}"
        )
        if not (len(image_urls) == len(image_colors) == len(image_color_codes)):
            raise ProductImageProcessingError(
                "Image metadata lists (images, colors, color_codes) must have the same length"
            )

        return [
            ImageType(
                image_url=image_urls[i],
                image_color=image_colors[i],
                image_color_code=image_color_codes[i],
            )
            for i in range(len(image_urls))
        ]


image_processing_manager = ImageProcessingManager()
