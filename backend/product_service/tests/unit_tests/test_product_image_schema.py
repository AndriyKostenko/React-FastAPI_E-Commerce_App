from uuid import uuid4

from schemas.product_image_schema import ImageType, ProductImageSchema


def test_supplier_images_allow_missing_color_metadata() -> None:
    image = ImageType(
        image_url="https://example.com/product.jpg",
        image_color=None,
        image_color_code=None,
    )
    stored_image = ProductImageSchema(
        id=uuid4(),
        product_id=uuid4(),
        image_url=image.image_url,
        image_color=None,
        image_color_code=None,
    )

    assert image.image_color is None
    assert stored_image.image_color_code is None
