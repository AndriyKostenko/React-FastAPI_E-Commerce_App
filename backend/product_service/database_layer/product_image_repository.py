from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer.database_layer import BaseRepository
from models.product_image_models import ProductImage


class ProductImageRepository(BaseRepository[ProductImage]):
    """
    This class extends BaseRepository to provide specific methods
    for managing product images in the database.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductImage)

    async def delete_by_product_id(self, product_id: UUID) -> None:
        """Delete all images for a given product."""
        stmt = delete(ProductImage).where(ProductImage.product_id == product_id)
        await self.session.execute(stmt)
