from pydantic import HttpUrl
from schemas.product_schemas import ImageType


async def create_image_metadata(image_paths: list[str], images_color: list[str], images_color_code: list[str]):
    return [
        ImageType(
            image_color=images_color[i],
            image_color_code=images_color_code[i],
            image_url=path
        )
        for i, path in enumerate(image_paths)
    ]
