from uuid import UUID

from pydantic import BaseModel, ConfigDict

from storage.catalogue_url import CatalogueImageUrl


class ProductImageSchema(BaseModel):
    """Schema for product image representation (responses)."""

    id: UUID
    product_id: UUID
    image_url: CatalogueImageUrl
    image_color: str | None = None
    image_color_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ImageType(BaseModel):
    """An image row to write: ``image_url`` is the stored key or URL as is."""

    image_color: str | None = None
    image_color_code: str | None = None
    image_url: str

    model_config = ConfigDict(from_attributes=True)


class ProductImageView(ImageType):
    """An image in a product response, with a URL the browser can load."""

    image_url: CatalogueImageUrl
