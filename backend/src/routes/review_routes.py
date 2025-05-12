from typing import List, Annotated, Dict, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File, Body, Query
from requests import session
from sqlalchemy.ext.asyncio import AsyncSession
import os
from src.dependencies.dependencies import get_db_session
from src.security.authentication import auth_manager
from src.service.product_service import ProductCRUDService
from src.schemas.product_schemas import CreateProduct
from src.schemas.review_schemas import CreateProductReview
from src.service.review_service import ReviewCRUDService




review_routes = APIRouter(
    tags=["review"]
)

@review_routes.get("/review/product/{product_id}")
async def get_product_reviews(product_id: str,
                              db: AsyncSession = Depends(get_db_session)):
    return await ReviewCRUDService(session=db).get_product_reviews(product_id)


@review_routes.post("/review/product/{product_id}", response_model=CreateProductReview, status_code=status.HTTP_201_CREATED)
async def create_product_review(product_id: str,
                                review: CreateProductReview,
                                db: AsyncSession = Depends(get_db_session),
                                current_user: dict = Depends(auth_manager.get_current_user_from_token)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You need to be logged in to review a product")

    # Check if the product exists
    product = await ProductCRUDService(session=db).get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Check if the user already reviewed this product
    existing_review = await ReviewCRUDService(session=db).get_product_review_by_user_id(product_id, current_user["id"])
    if existing_review:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already reviewed this product")

    # Proceed with creating the review if no existing review is found
    new_review = await ReviewCRUDService(session=db).create_product_review(review=review)
    return new_review

@review_routes.put("/product/{product_id}/review/{review_id}", response_model=CreateProductReview)
async def update_product_review(product_id: str,
                                review_id: str,
                                review: CreateProductReview,
                                db: AsyncSession = Depends(get_db_session),
                                current_user: dict = Depends(auth_manager.get_current_user_from_token)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You need to be logged in to update a review")
    product = await ProductCRUDService(session=db).get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    review = await ReviewCRUDService(session=db).get_review_by_id(review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review['user_id'] != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own reviews")
    return await ReviewCRUDService(session=db).update_product_review(review_id, review)


@review_routes.delete("/product/{product_id}/review/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_review(product_id: str,
                                review_id: str,
                                db: AsyncSession = Depends(get_db_session),
                                current_user: dict = Depends(auth_manager.get_current_user_from_token)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You need to be logged in to delete a review")
    product = await ProductCRUDService(session=db).get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    review = await ReviewCRUDService(session=db).get_review_by_id(review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review['user_id'] != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own reviews")
    return  await ReviewCRUDService(session=db).delete_product_review(review_id)
