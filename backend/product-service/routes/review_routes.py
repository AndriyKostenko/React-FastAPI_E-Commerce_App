from uuid import UUID
from typing import List

from fastapi import APIRouter, status, HTTPException

from schemas.review_schemas import ReviewSchema, CreateReview, UpdateReview
from dependencies.dependencies import review_service_dependency, product_service_dependency


review_routes = APIRouter(
    tags=["reviews"]
)

@review_routes.post("/products/{product_id}/users/{user_id}/reviews", 
                   response_model=ReviewSchema, 
                   status_code=status.HTTP_201_CREATED)
async def create_product_review(
    product_id: UUID,
    user_id: UUID,
    review: CreateReview,
    review_service: review_service_dependency,
    product_service: product_service_dependency
) -> ReviewSchema:
    # Verify product exists
    await product_service.get_product_by_id(product_id=product_id)
    return await review_service.create_product_review(user_id=user_id, product_id=product_id, data=review)


@review_routes.get("/reviews/",
                   status_code=status.HTTP_200_OK,
                   response_model=List[ReviewSchema])
async def get_all_reviews(review_service: review_service_dependency) -> List[ReviewSchema]:
    return await review_service.get_all_reviews()
    

@review_routes.get("/products/{product_id}/reviews/{review_id}",
                   status_code=status.HTTP_200_OK,
                   response_model=ReviewSchema)
async def get_review_by_id(review_id: UUID,
                           review_service: review_service_dependency) -> ReviewSchema:
    return await review_service.get_review_by_id(review_id=review_id)


@review_routes.get("/products/{product_id}/reviews",
                   status_code=status.HTTP_200_OK,
                   response_model=list[ReviewSchema])
async def get_reviews_by_product_id(product_id: UUID,
                                    review_service: review_service_dependency) -> list[ReviewSchema]:
    return await review_service.get_reviews_by_product_id(product_id=product_id)


@review_routes.get("/users/{user_id}/reviews",
                   status_code=status.HTTP_200_OK,
                   response_model=list[ReviewSchema])
async def get_reviews_by_user_id(user_id: UUID,
                                 review_service: review_service_dependency) -> list[ReviewSchema]:
    return await review_service.get_reviews_by_user_id(user_id=user_id)


@review_routes.get("/products/{product_id}/users/{user_id}/reviews",
                   status_code=status.HTTP_200_OK,
                   response_model=ReviewSchema)
async def get_review_by_product_id_and_user_id(product_id: UUID,
                                               user_id: UUID,
                                               review_service: review_service_dependency) -> ReviewSchema:
    return await review_service.get_review_by_product_id_and_user_id(product_id=product_id, 
                                                                     user_id=user_id)


@review_routes.put("/products/{product_id}/users/{user_id}/reviews", 
                  response_model=ReviewSchema,
                  status_code=status.HTTP_200_OK)
async def update_product_review(
    product_id: UUID,
    user_id: UUID,
    review_data: UpdateReview,
    review_service: review_service_dependency,
    product_service: product_service_dependency
) -> ReviewSchema:
    # Verify product exists
    await product_service.get_product_by_id(product_id=product_id)
    
    # Verify existing review
    await review_service.get_review_by_product_id_and_user_id(
        product_id=product_id,
        user_id=user_id
    )

    return await review_service.update_product_review(
        product_id=product_id,
        user_id=user_id,
        update_data=review_data
    )


@review_routes.delete("/products/{product_id}/users/{user_id}/reviews",
                     status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_review(
    product_id: UUID,
    user_id: UUID,
    review_service: review_service_dependency,
    product_service: product_service_dependency
) -> None:
    # Verify product exists
    await product_service.get_product_by_id(product_id=product_id)
    
    # Get existing review
    existing_review = await review_service.get_review_by_product_id_and_user_id(
        product_id=product_id,
        user_id=user_id
    )
    
    await review_service.delete_product_review(review_id=existing_review.id)
