from uuid import UUID
from typing import Any, List

from fastapi import APIRouter, status, Request

from shared.schemas.review_schemas import ReviewSchema, CreateReview, UpdateReview
from dependencies.dependencies import review_service_dependency, product_service_dependency
from models.review_models import ProductReview


review_routes = APIRouter(
    tags=["reviews"]
)


@review_routes.post("/products/{product_id}/users/{user_id}/reviews",
                   response_model=ReviewSchema,
                   response_description="Create product review",
                   status_code=status.HTTP_201_CREATED)
async def create_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                review: CreateReview,
                                review_service: review_service_dependency,
                                product_service: product_service_dependency
                            ) -> ReviewSchema:
    created_review = await review_service.create_product_review(user_id=user_id, product_id=product_id, data=review)
    return created_review


@review_routes.get("/reviews",
                   response_model=List[ReviewSchema],
                   response_description="Get all reviews",
                   status_code=status.HTTP_200_OK)
async def get_all_reviews(request: Request,
                         review_service: review_service_dependency) -> list[ReviewSchema]:
    reviews = await review_service.get_all_reviews()
    return reviews


@review_routes.get("/reviews/{review_id}",
                   response_model=ReviewSchema,
                   response_description="Get review by ID",
                   status_code=status.HTTP_200_OK)
async def get_review_by_id(request: Request,
                          review_id: UUID,
                          review_service: review_service_dependency) -> ReviewSchema:
    review = await review_service.get_review_by_id(review_id=review_id)
    return review


@review_routes.get("/products/{product_id}/reviews",
                   response_model=list[ReviewSchema],
                   response_description="Get all reviews for a product",
                   status_code=status.HTTP_200_OK)
async def get_reviews_by_product_id(request: Request,
                                   product_id: UUID,
                                   review_service: review_service_dependency) -> list[ReviewSchema]:
    reviews = await review_service.get_reviews_by_product_id(product_id=product_id)
    return reviews


@review_routes.get("/users/{user_id}/reviews",
                   response_model=list[ReviewSchema],
                   response_description="Get all reviews by user",
                   status_code=status.HTTP_200_OK)
async def get_reviews_by_user_id(request: Request,
                                user_id: UUID,
                                review_service: review_service_dependency) -> list[ReviewSchema]:
    reviews = await review_service.get_reviews_by_user_id(user_id=user_id)
    return reviews


@review_routes.get("/products/{product_id}/users/{user_id}/reviews",
                   response_model=ReviewSchema,
                   response_description="Get specific user's review for a product",
                   status_code=status.HTTP_200_OK)
async def get_review_by_product_id_and_user_id(request: Request,
                                               product_id: UUID,
                                               user_id: UUID,
                                               review_service: review_service_dependency) -> ReviewSchema:
    review = await review_service.get_review_by_product_id_and_user_id(product_id=product_id,
                                                                      user_id=user_id)
    return review


@review_routes.put("/products/{product_id}/users/{user_id}/reviews",
                  response_model=ReviewSchema,
                  response_description="Update product review",
                  status_code=status.HTTP_200_OK)
async def update_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                review_data: UpdateReview,
                                review_service: review_service_dependency) -> ReviewSchema:
    updated_review = await review_service.update_product_review(
        product_id=product_id,
        user_id=user_id,
        update_data=review_data
    )
    return updated_review


@review_routes.delete("/products/{product_id}/users/{user_id}/reviews",
                     response_description="Delete product review",
                     response_model=None,
                     status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                review_service: review_service_dependency) -> None:
    existing_review = await review_service.get_review_by_product_id_and_user_id(
        product_id=product_id,
        user_id=user_id
    )
    await review_service.delete_product_review(review_id=existing_review.id)
    return None

@review_routes.get(
    "/admin/schema/reviews",
    summary="Schema for AdminJS",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_product_reviews_schema_for_admin_js(request: Request):
    return {"fields": ProductReview.get_admin_schema()}
