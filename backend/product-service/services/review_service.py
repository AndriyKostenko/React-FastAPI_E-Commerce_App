from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.review_models import ProductReview
from schemas.review_schemas import CreateReview, ReviewSchema, AllReviewsSchema
from errors.review_errors import ReviewNotFoundError


class ReviewCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product_review(self, review: CreateReview) -> ReviewSchema:
        product_review = ProductReview(
            user_id=review.user_id,
            product_id=review.product_id,
            comment=review.comment,
            rating=review.rating
        )
        self.session.add(product_review)
        await self.session.commit()
        return ReviewSchema.model_validate(product_review)

    async def get_review_by_id(self, review_id: UUID) -> ReviewSchema:
        result = await self.session.execute(select(ProductReview).filter(ProductReview.id == review_id))
        review = result.scalars().first()
        if not review:
            raise ReviewNotFoundError(f"Review with ID: {review_id} not found.")
        return ReviewSchema.model_validate(review)

    async def get_product_review_by_user_id(self, product_id: UUID, user_id: UUID) -> AllReviewsSchema:
        result = await self.session.execute(select(ProductReview).filter(ProductReview.product_id == product_id).filter(ProductReview.user_id == user_id))
        reviews = result.scalars().all()
        if not reviews:
            return ReviewNotFoundError(f"No reviews found for product ID: {product_id} by user ID: {user_id}.")
        return AllReviewsSchema(reviews=[ReviewSchema.model_validate(review) for review in reviews])

    async def get_product_reviews(self, product_id: UUID) -> AllReviewsSchema:
        result = await self.session.execute(select(ProductReview).filter(ProductReview.product_id == product_id))
        reviews = result.scalars().all()
        if not reviews:
            raise ReviewNotFoundError(f"No reviews found for product ID: {product_id}.")
        return AllReviewsSchema(reviews=[ReviewSchema.model_validate(review) for review in reviews])

    async def update_product_review(self, review_id: UUID, update_data: CreateReview) -> ReviewSchema:
        review = await self.get_review_by_id(review_id)
        review.comment = update_data.comment
        review.rating = update_data.rating
        await self.session.commit()
        await self.session.refresh(review)
        return ReviewSchema.model_validate(review)

    async def delete_product_review(self, review_id: UUID) -> None:
        product_review = await self.get_review_by_id(review_id)
        await self.session.delete(product_review)
        await self.session.commit()



