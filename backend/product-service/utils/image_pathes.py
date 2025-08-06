import os
from typing import List
from datetime import datetime
from fastapi import UploadFile


# Ensure the media directories exist
MEDIA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../media/images'))
ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../media/icons'))
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(ICONS_DIR, exist_ok=True)

# The base URLs for serving media files (you can configure this based on your FastAPI setup)
BASE_MEDIA_URL = "/media/images"
BASE_ICONS_URL = "/media/icons"


def safe_splitext(filename: str | None) -> tuple[str, str]:
    """Safely split filename, handling None values"""
    if filename is None:
        return "unknown", ""
    return os.path.splitext(filename)


async def create_image_paths(images: List[UploadFile]):
    image_paths = []

    for image in images:
        now = datetime.now()
        date_time_str = now.strftime("%Y%m%d_%H%M%S")

        # Split the original filename to get the name and extension
        name, ext = safe_splitext(image.filename)

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


        # Return the relative URL instead of the absolute file path
        image_url = f"{base_url}/{new_filename}"
        image_paths.append(image_url)

    return image_paths