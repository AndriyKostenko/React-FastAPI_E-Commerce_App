from sqlalchemy.ext.asyncio import AsyncSession
from src.models.review_models import ProductReview
from sqlalchemy import select
from src.schemas.review_schemas import CreateProductReview


class ReviewCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product_review(self, review: CreateProductReview):
        product_review = ProductReview(
            user_id=review.user_id,
            product_id=review.product_id,
            comment=review.comment if review.comment is not None else "",
            rating=review.rating if review.rating is not None else 0.0
        )
        self.session.add(product_review)
        await self.session.commit()
        return product_review

    async def get_review_by_id(self, review_id: str):
        stmt = select(ProductReview).filter(ProductReview.id == review_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_product_reviews(self, product_id: str):
        stmt = select(ProductReview).filter(ProductReview.product_id == product_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_product_review(self, review_id: str, review: CreateProductReview):
        stmt = select(ProductReview).filter(ProductReview.id == review_id)
        result = await self.session.execute(stmt)
        product_review = result.scalars().first()
        if product_review:
            if review.comment is not None:
                product_review.comment = review.comment
            if review.rating is not None:
                product_review.rating = review.rating
            await self.session.commit()
        return product_review

    async def delete_product_review(self, review_id: str):
        stmt = select(ProductReview).filter(ProductReview.id == review_id)
        result = await self.session.execute(stmt)
        product_review = result.scalars().first()
        if product_review:
            await self.session.delete(product_review)
            await self.session.commit()
        return product_review


