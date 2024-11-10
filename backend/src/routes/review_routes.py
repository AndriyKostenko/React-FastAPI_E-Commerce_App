from typing import List, Annotated, Dict, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File, Body, Query
from requests import session
from sqlalchemy.ext.asyncio import AsyncSession
import os
from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.product_service import ProductCRUDService
from src.schemas.product_schemas import CreateProduct, GetAllProducts, CreateProductReview
from src.utils.image_metadata import create_image_metadata
from src.utils.image_pathes import create_image_paths




rating_routes = APIRouter(
    tags=["product"]
)


@rating_routes.post("/product/{product_id}/rating", response_model=CreateProductReview, status_code=status.HTTP_201_CREATED)
async def create_product_rating(product_id: str, review: CreateProductReview, db: AsyncSession = Depends(get_db_session), current_user: dict = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You need to be logged in to rate a product")
    product = await ProductCRUDService(session=db).get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return await ReviewCRUDService(session=db).create_product_review(product_id, review, current_user)