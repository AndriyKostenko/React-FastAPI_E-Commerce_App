"""ProductImageService: replacing images must not delete the old ones first."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from service_layer.product_image_service import ProductImageService
from exceptions.product_image_exceptions import ProductImageProcessingError


async def test_invalid_uploads_leave_the_existing_images_alone() -> None:
    repository = MagicMock()
    repository.delete_many_by_field = AsyncMock(return_value=3)
    repository.create_many = AsyncMock()
    service = ProductImageService(repository)

    # One file, no colour metadata: rejected while validating the uploads.
    with pytest.raises(ProductImageProcessingError):
        await service.replace_product_images(
            product_id=uuid4(), images=[MagicMock()], image_colors=[], color_codes=[]
        )

    # The old images used to be deleted before the uploads were even checked.
    repository.delete_many_by_field.assert_not_called()
    repository.create_many.assert_not_called()
