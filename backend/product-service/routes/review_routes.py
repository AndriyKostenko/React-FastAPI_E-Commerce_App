from uuid import UUID
from fastapi import Depends, APIRouter, status, HTTPException

from schemas.review_schemas import ReviewSchema, CreateReview
from dependencies import review_crud_dependency, product_crud_dependency


review_routes = APIRouter(
    tags=["review"]
)

@review_routes.get("/review/product/{product_id}",
                   status_code=status.HTTP_200_OK,
                   response_model=ReviewSchema)
async def get_product_reviews(product_id: UUID,
                              review_crud_service: review_crud_dependency):
    return await review_crud_service.get_product_reviews(product_id=product_id)


@review_routes.post("/review/product/{product_id}", 
                    response_model=ReviewSchema, 
                    status_code=status.HTTP_201_CREATED)
async def create_product_review(product_id: UUID,
                                review: CreateReview,
                                review_crud_service: review_crud_dependency,
                                product_crud_service: product_crud_dependency,
                                current_user_id: UUID):

    product = await product_crud_service.get_product_by_id(product_id=product_id)
    
    # Check if the user already reviewed this product
    existing_review = await review_crud_service.get_product_review_by_user_id(product.id, current_user_id)
    if existing_review:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already reviewed this product")

    # Proceed with creating the review if no existing review is found
    new_review = await review_crud_service.create_product_review(review=review)
    return new_review

@review_routes.put("/product/{product_id}/review/{review_id}",
                    status_code=status.HTTP_200_OK, 
                    response_model=ReviewSchema)
async def update_product_review(product_id: UUID,
                                review_id: UUID,
                                review: CreateReview,
                                review_crud_service: review_crud_dependency,
                                product_crud_service: product_crud_dependency,
                                current_user_id: UUID) -> ReviewSchema:

    product = await product_crud_service.get_product_by_id(product_id)
    review = await review_crud_service.get_review_by_id(review_id)
    return await review_crud_service.update_product_review(review.id, review)


@review_routes.delete("/product/{product_id}/review/{review_id}",
                      status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_review(product_id: UUID,
                                review_id: UUID,
                                review_crud_service: review_crud_dependency,
                                product_crud_service: product_crud_dependency,
                                current_user_id: UUID,):

    product = await product_crud_service.get_product_by_id(product_id)
    review = await review_crud_service.get_review_by_id(review_id)
    return  await review_crud_service.delete_product_review(review_id)
