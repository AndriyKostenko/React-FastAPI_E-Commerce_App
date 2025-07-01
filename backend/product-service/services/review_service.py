from uuid import UUID
from typing import List, Optional

from schemas.review_schemas import CreateReview, ReviewSchema, UpdateReview
from errors.review_errors import ReviewNotFoundError, ReviewAlreadyExistsError
from repositories.review_repository import ReviewRepository
from models.review_models import ProductReview


class ReviewService:
    """Service layer for review management operations, business logic and data validation."""
    def __init__(self, repo: ReviewRepository):
        self.repo = repo

    async def create_product_review(self, user_id: UUID, product_id: UUID, data: CreateReview) -> ReviewSchema:
        # Check if review already exists
        existing_review = await self.repo.get_review_by_product_and_user_id(
            product_id=product_id,
            user_id=user_id
        )
        if existing_review:
            raise ReviewAlreadyExistsError(f"User with id: {user_id} has already reviewed product id: {product_id}")
        
        product_review = ProductReview(
            product_id=product_id,
            user_id=user_id,
            comment=data.comment,
            rating=data.rating
        )
        product_review = await self.repo.add_review(product_review)
        return ReviewSchema.model_validate(product_review)


    async def get_review_by_id(self, review_id: UUID) -> ReviewSchema:
        db_review = await self.repo.get_review_by_id(review_id)
        if not db_review:
            raise ReviewNotFoundError(f"Review with ID: {review_id} not found.")
        return ReviewSchema.model_validate(db_review)


    async def get_reviews_by_user_id(self, user_id: UUID) -> List[ReviewSchema]:
        db_reviews = await self.repo.get_reviews_by_user_id(user_id)
        if not db_reviews:
            raise ReviewNotFoundError(f"No reviews found for user with ID: {user_id}")
        return [ReviewSchema.model_validate(review) for review in db_reviews]
    
    
    async def get_reviews_by_product_id(self, product_id: UUID) -> List[ReviewSchema]:
        db_reviews = await self.repo.get_reviews_by_product_id(product_id)
        if not db_reviews:
            raise ReviewNotFoundError(f"No reviews found for product with ID: {product_id}")
        return [ReviewSchema.model_validate(review) for review in db_reviews]


    async def get_review_by_product_id_and_user_id(self, product_id: UUID, user_id: UUID) -> ReviewSchema:
        """Get review if exists, return None if not found"""
        db_review = await self.repo.get_review_by_product_and_user_id(product_id, user_id)
        if not db_review:
            raise ReviewNotFoundError(
                f"Review for product id: {product_id} by user id: {user_id} not found"
            )
        return ReviewSchema.model_validate(db_review)
    
    async def get_all_reviews(self) -> List[ReviewSchema]:
        """Get all reviews in the system"""
        db_reviews = await self.repo.get_all_reviews()
        if not db_reviews:
            raise ReviewNotFoundError("No reviews found in the system.")
        return [ReviewSchema.model_validate(review) for review in db_reviews]


    async def update_product_review(self, product_id: UUID, user_id: UUID, update_data: UpdateReview) -> ReviewSchema:
        existing_review = await self.repo.get_review_by_product_and_user_id(product_id, user_id)
        if not existing_review:
            raise ReviewNotFoundError(
                f"Review for product id: {product_id} by user id: {user_id} not found"
            )
        
        # Update fields
        existing_review.comment = update_data.comment
        existing_review.rating = update_data.rating
        
        updated_review = await self.repo.update_review(existing_review)
        return ReviewSchema.model_validate(updated_review)


    async def delete_product_review(self, review_id: UUID) -> None:
        db_review = await self.repo.get_review_by_id(review_id)
        if not db_review:
            raise ReviewNotFoundError(f"Review with ID: {review_id} not found.")
        await self.repo.delete_review(db_review)    



