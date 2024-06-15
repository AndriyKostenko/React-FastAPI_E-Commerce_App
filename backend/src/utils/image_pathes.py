import os
from typing import List
from datetime import datetime
from fastapi import UploadFile
from PIL import Image

# Ensure the media directory exists
MEDIA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../media/images'))
os.makedirs(MEDIA_DIR, exist_ok=True)


async def create_image_paths(images: List[UploadFile]):
    image_paths = []

    for image in images:
        now = datetime.now()
        date_time_str = now.strftime("%Y%m%d_%H%M%S")

        # Split the original filename to get the name and extension
        name, ext = os.path.splitext(image.filename)

        # Create a new filename with the date and time appended
        new_filename = f"{name}_{date_time_str}{ext}"
        file_path = os.path.join(MEDIA_DIR, new_filename)
        file_path = os.path.abspath(file_path)

        # Resize and compress the image
        with Image.open(image.file) as img:
            # Resize the image to a maximum size of 800x600
            max_size = (800, 600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save the resized and compressed image
            img.save(file_path, quality=70, optimize=True)

        image_paths.append(file_path)
    return image_paths
