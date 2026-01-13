from uuid import UUID
from typing import List

from shared.schemas.review_schemas import CreateReview, ReviewSchema, UpdateReview
from exceptions.review_exceptions import ReviewNotFoundError, ReviewAlreadyExistsError
from models.review_models import ProductReview
from database_layer.review_repository import ReviewRepository


class ReviewService:
    """Service layer for review management operations, business logic and data validation."""
    def __init__(self, repository: ReviewRepository):
        self.repository = repository


    async def create_product_review(self, user_id: UUID, product_id: UUID, data: CreateReview) -> ReviewSchema:
        # Check if review already exists
        existing_review = await self.repository.filter_by(product_id=product_id, user_id=user_id)
        if existing_review:
            raise ReviewAlreadyExistsError(f"User with id: {user_id} has already reviewed product id: {product_id}")

        product_review = ProductReview(
            product_id=product_id,
            user_id=user_id,
            comment=data.comment,
            rating=data.rating
        )
        product_review = await self.repository.create(product_review)
        return ReviewSchema.model_validate(product_review)


    async def get_review_by_id(self, review_id: UUID) -> ReviewSchema:
        db_review = await self.repository.get_by_id(review_id)
        if not db_review:
            raise ReviewNotFoundError(f"Review with ID: {review_id} not found.")
        return ReviewSchema.model_validate(db_review)


    async def get_reviews_by_user_id(self, user_id: UUID) -> List[ReviewSchema]:
        db_reviews = await self.repository.get_many_by_field(field_name="user_id", value=user_id)
        if not db_reviews:
            raise ReviewNotFoundError(f"No reviews found for user with ID: {user_id}")
        return [ReviewSchema.model_validate(review) for review in db_reviews]


    async def get_reviews_by_product_id(self, product_id: UUID) -> List[ReviewSchema]:
        db_reviews = await self.repository.get_many_by_field(field_name="product_id", value=product_id)
        if not db_reviews:
            raise ReviewNotFoundError(f"No reviews found for product with ID: {product_id}")
        return [ReviewSchema.model_validate(review) for review in db_reviews]


    async def get_review_by_product_id_and_user_id(self, product_id: UUID, user_id: UUID) -> ReviewSchema:
        """Get review if exists, return None if not found"""
        db_reviews = await self.repository.filter_by(product_id=product_id, user_id=user_id)
        if not db_reviews:
            raise ReviewNotFoundError(
                f"Review for product id: {product_id} by user id: {user_id} not found"
            )
        # Should only be one review per user per product
        return ReviewSchema.model_validate(db_reviews[0])


    async def get_all_reviews(self) -> List[ReviewSchema]:
        """Get all reviews in the system"""
        db_reviews = await self.repository.get_all()
        if not db_reviews:
            raise ReviewNotFoundError("No reviews found in the system.")
        return [ReviewSchema.model_validate(review) for review in db_reviews]


    async def update_product_review(self, product_id: UUID, user_id: UUID, update_data: UpdateReview) -> ReviewSchema:
        existing_reviews = await self.repository.filter_by(product_id=product_id, user_id=user_id)
        if not existing_reviews:
            raise ReviewNotFoundError(
                f"Review for product id: {product_id} by user id: {user_id} not found"
            )

        # Update fields
        existing_review = existing_reviews[0]
        if update_data.comment is not None:
            existing_review.comment = update_data.comment
        if update_data.rating is not None:
            existing_review.rating = update_data.rating

        updated_review = await self.repository.update(existing_review)
        return ReviewSchema.model_validate(updated_review)


    async def delete_product_review(self, review_id: UUID) -> None:
        db_review = await self.repository.get_by_id(review_id)
        if not db_review:
            raise ReviewNotFoundError(f"Review with ID: {review_id} not found.")
        await self.repository.delete(db_review)
