import os
from typing import List
from datetime import datetime
from fastapi import UploadFile

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
        with open(file_path, 'wb') as f:
            f.write(await image.read())
        image_paths.append(file_path)
    return image_paths
