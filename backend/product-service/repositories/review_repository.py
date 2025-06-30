from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc

from models.review_models import ProductReview


class ReviewRepository:
    """Handles direct DB access for ProductReview entity. No business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # CREATE
    async def add_review(self, review: ProductReview) -> ProductReview:
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    # READ
    async def get_all_reviews(self) -> list[ProductReview]:
        result = await self.session.execute(select(ProductReview).order_by(asc(ProductReview.id)))
        return result.scalars().all()

    async def get_review_by_id(self, review_id: UUID) -> Optional[ProductReview]:
        result = await self.session.execute(select(ProductReview).where(ProductReview.id == review_id))
        return result.scalars().first()

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

    # UPDATE
    async def update_review(self, review: ProductReview) -> ProductReview:
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    # DELETE
    async def delete_review(self, review: ProductReview) -> None:
        await self.session.delete(review)
        await self.session.commit()