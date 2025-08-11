from uuid import UUID
from typing import List

from fastapi import APIRouter, status, Request

from schemas.review_schemas import ReviewSchema, CreateReview, UpdateReview
from dependencies.dependencies import review_service_dependency, product_service_dependency
from shared.customized_json_response import JSONResponse
from shared.shared_instances import product_service_redis_manager


review_routes = APIRouter(
    tags=["reviews"]
)


@review_routes.post("/products/{product_id}/users/{user_id}/reviews", 
                   response_model=ReviewSchema, 
                   response_description="Create product review")
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                review: CreateReview,
                                review_service: review_service_dependency,
                                product_service: product_service_dependency
                            ) -> JSONResponse:
    created_review = await review_service.create_product_review(user_id=user_id, product_id=product_id, data=review)
    # Invalidate cache after creation
    await product_service_redis_manager.invalidate_cache(request=request)
    return JSONResponse(
        content=created_review,
        status_code=status.HTTP_201_CREATED
    )


@review_routes.get("/reviews",
                   response_model=List[ReviewSchema],
                   response_description="Get all reviews")
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_all_reviews(request: Request,
                         review_service: review_service_dependency) -> JSONResponse:
    reviews = await review_service.get_all_reviews()
    return JSONResponse(
        content=reviews,
        status_code=status.HTTP_200_OK
    )


@review_routes.get("/reviews/{review_id}",
                   response_model=ReviewSchema,
                   response_description="Get review by ID")
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_review_by_id(request: Request,
                          review_id: UUID,
                          review_service: review_service_dependency) -> JSONResponse:
    review = await review_service.get_review_by_id(review_id=review_id)
    return JSONResponse(
        content=review,
        status_code=status.HTTP_200_OK
    )


@review_routes.get("/products/{product_id}/reviews",
                   response_model=list[ReviewSchema],
                   response_description="Get all reviews for a product")
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_reviews_by_product_id(request: Request,
                                   product_id: UUID,
                                   review_service: review_service_dependency) -> JSONResponse:
    reviews = await review_service.get_reviews_by_product_id(product_id=product_id)
    return JSONResponse(
        content=reviews,
        status_code=status.HTTP_200_OK
    )


@review_routes.get("/users/{user_id}/reviews",
                   response_model=list[ReviewSchema],
                   response_description="Get all reviews by user")
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_reviews_by_user_id(request: Request,
                                user_id: UUID,
                                review_service: review_service_dependency) -> JSONResponse:
    reviews = await review_service.get_reviews_by_user_id(user_id=user_id)
    return JSONResponse(
        content=reviews,
        status_code=status.HTTP_200_OK
    )


@review_routes.get("/products/{product_id}/users/{user_id}/reviews",
                   response_model=ReviewSchema,
                   response_description="Get specific user's review for a product")
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_review_by_product_id_and_user_id(request: Request,
                                               product_id: UUID,
                                               user_id: UUID,
                                               review_service: review_service_dependency) -> JSONResponse:
    review = await review_service.get_review_by_product_id_and_user_id(product_id=product_id, 
                                                                       user_id=user_id)
    return JSONResponse(
        content=review,
        status_code=status.HTTP_200_OK
    )


@review_routes.put("/products/{product_id}/users/{user_id}/reviews", 
                  response_model=ReviewSchema,
                  response_description="Update product review")
@product_service_redis_manager.ratelimiter(times=20, seconds=60)
async def update_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                review_data: UpdateReview,
                                review_service: review_service_dependency) -> JSONResponse:
    updated_review = await review_service.update_product_review(
        product_id=product_id,
        user_id=user_id,
        update_data=review_data
    )

    # Clear ALL review-related cache
    await product_service_redis_manager.clear_cache_namespace(namespace="/api/v1/reviews")
    return JSONResponse(
        content=updated_review,
        status_code=status.HTTP_200_OK
    )


@review_routes.delete("/products/{product_id}/users/{user_id}/reviews",
                     response_description="Delete product review")
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def delete_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                review_service: review_service_dependency) -> JSONResponse:
    # Get existing review
    existing_review = await review_service.get_review_by_product_id_and_user_id(
        product_id=product_id,
        user_id=user_id
    )
    await review_service.delete_product_review(review_id=existing_review.id)
    # Clear ALL review-related cache
    await product_service_redis_manager.clear_cache_namespace(namespace="/api/v1/reviews")
    
    return JSONResponse(
        content={"message": "Review deleted successfully"},
        status_code=status.HTTP_204_NO_CONTENT
    )