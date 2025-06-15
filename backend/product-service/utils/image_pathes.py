import os
from typing import List
from datetime import datetime
from fastapi import UploadFile
from PIL import Image

# Ensure the media directories exist
MEDIA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../media/images'))
ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../media/icons'))
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(ICONS_DIR, exist_ok=True)

# The base URLs for serving media files (you can configure this based on your FastAPI setup)
BASE_MEDIA_URL = "/media/images"
BASE_ICONS_URL = "/media/icons"

async def create_image_paths(images: List[UploadFile]):
    image_paths = []

    for image in images:
        now = datetime.now()
        date_time_str = now.strftime("%Y%m%d_%H%M%S")

        # Split the original filename to get the name and extension
        name, ext = os.path.splitext(image.filename)

        # Determine the directory and base URL based on the file extension
        if ext.lower() == ".svg":
            directory = ICONS_DIR
            base_url = BASE_ICONS_URL
        else:
            directory = MEDIA_DIR
            base_url = BASE_MEDIA_URL

        # Create a new filename with the date and time appended
        new_filename = f"{name}_{date_time_str}{ext}"
        file_path = os.path.join(directory, new_filename)
        file_path = os.path.abspath(file_path)

        if ext.lower() != ".svg":
            # Resize and compress the image if it's not an SVG
            with Image.open(image.file) as img:
                # Resize the image to a maximum size of 800x600
                max_size = (800, 600)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

                # Save the resized and compressed image
                img.save(file_path, quality=70, optimize=True)
        else:
            # Save the SVG file directly
            with open(file_path, "wb") as buffer:
                buffer.write(await image.read())

        # Return the relative URL instead of the absolute file path
        image_url = f"{base_url}/{new_filename}"
        image_paths.append(image_url)

    return image_paths