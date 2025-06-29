from uuid import UUID
from typing import List

from fastapi import APIRouter, status, HTTPException

from schemas.review_schemas import ReviewSchema, CreateReview, UpdateReview
from dependencies.dependencies import review_crud_dependency, product_crud_dependency


review_routes = APIRouter(
    tags=["review"]
)

@review_routes.get("/review/product/{product_id}",
                   status_code=status.HTTP_200_OK,
                   response_model=List[ReviewSchema])
async def get_product_reviews(product_id: UUID,
                              review_crud_service: review_crud_dependency) -> List[ReviewSchema]:
    return await review_crud_service.get_product_reviews(product_id=product_id)


@review_routes.post("/review/product/{product_id}", 
                    response_model=ReviewSchema, 
                    status_code=status.HTTP_201_CREATED)
async def create_product_review(review: CreateReview,
                                review_crud_service: review_crud_dependency,
                                product_crud_service: product_crud_dependency):
    # cheking if product exists
    await product_crud_service.get_product_by_id(product_id=review.product_id)

    return await review_crud_service.create_product_review(review=review)


@review_routes.put("/product/{product_id}/review/{review_id}",
                    status_code=status.HTTP_200_OK, 
                    response_model=ReviewSchema)
async def update_product_review(review: UpdateReview,
                                review_crud_service: review_crud_dependency,
                                product_crud_service: product_crud_dependency) -> ReviewSchema:
    # cheking if product exists
    await product_crud_service.get_product_by_id(product_id=review.product_id)
    
    db_review = await review_crud_service.get_review_by_id(review_id=review.)
    
    return await review_crud_service.update_product_review(db_review.id, review)


@review_routes.delete("/product/{product_id}/review/{review_id}",
                      status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_review(product_id: UUID,
                                review_id: UUID,
                                review_crud_service: review_crud_dependency,
                                product_crud_service: product_crud_dependency,
                                current_user_id: UUID,):
    # cheking if product exists
    await product_crud_service.get_product_by_id(product_id)
    
    await review_crud_service.get_review_by_id(review_id)
    return await review_crud_service.delete_product_review(review_id)
