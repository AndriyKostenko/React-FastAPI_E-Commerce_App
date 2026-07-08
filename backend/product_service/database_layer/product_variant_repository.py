from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.product_variant_models import ProductVariant
from shared.database_layer.database_layer import BaseRepository


class ProductVariantRepository(BaseRepository[ProductVariant]):
    """Repository for product variant specific database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductVariant)

    async def delete_by_product_id(self, product_id: UUID) -> None:
        """Delete all variants for a given product."""
        stmt = delete(ProductVariant).where(ProductVariant.product_id == product_id)
        await self.session.execute(stmt)
