from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc

from models.review_models import ProductReview
from shared.database_layer import BaseRepository


class ReviewRepository(BaseRepository):
    """
    Review-specific repository with additional methods.
    Inherits from BaseRepository to manage database CRUD operations for Review entities.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductReview)
        self.session = session


    async def get_reviews_by_product_id(self, product_id: UUID) -> list[ProductReview]:
        result = await self.session.execute(select(ProductReview).where(ProductReview.product_id == product_id))
        return result.scalars().all()
    
    async def get_reviews_by_user_id(self, user_id: UUID) -> list[ProductReview]:
        result = await self.session.execute(select(ProductReview).where(ProductReview.user_id == user_id))
        return result.scalars().all()
    
    async def get_review_by_product_and_user_id(self, product_id: UUID, user_id: UUID) -> ProductReview:
        """Only one review per product per user."""
        result = await self.session.execute(
            select(ProductReview)
            .where(ProductReview.product_id == product_id) 
            .where(ProductReview.user_id == user_id)
        )
        return result.scalars().first()

 