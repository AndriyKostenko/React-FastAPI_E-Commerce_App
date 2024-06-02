from typing import List


async def create_image_metadata(image_paths: List[str], images_color: List[str], images_color_code: List[str]):
    return [
        {
            "color": images_color[i],
            "colorCode": images_color_code[i],
            "image": path,
        }
        for i, path in enumerate(image_paths)
    ]
