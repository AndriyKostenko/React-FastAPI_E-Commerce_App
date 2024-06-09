from typing import List, Annotated, Dict

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
import os
from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.product_service import ProductCRUDService
from src.schemas.product_schemas import CreateProduct, GetAllProducts, CreateProductReview
from src.utils.image_metadata import create_image_metadata
from src.utils.image_pathes import create_image_paths

product_routes = APIRouter(
    tags=["product"]
)


@product_routes.post("/create_new_product", status_code=status.HTTP_201_CREATED)
async def create_new_product(current_user: Annotated[dict, Depends(get_current_user)],
                             name: str = Form(...),
                             description: str = Form(...),
                             category: str = Form(...),
                             brand: str = Form(...),
                             quantity: str = Form(...),
                             price: str = Form(...),
                             in_stock: str = Form(...),
                             images_color: List[str] = Form(...),
                             images_color_code: List[str] = Form(...),
                             images: List[UploadFile] = File(...),
                             session: AsyncSession = Depends(get_db_session),
                             ):
    if current_user["user_role"] != "admin" or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # create image paths
    image_paths = await create_image_paths(images=images)

    # Validating that the lengths of the lists match....number of pict = color = color codes
    if len(image_paths) != len(images_color) or len(image_paths) != len(images_color_code):
        #TODO : so, i have to get data from Form from client and its separating data correctly in the list...but when
        # i do it from Swagger, all image_colors and image_color_codes are passed as a single string..so i have to split it

        # data will be passed as a single string with comas, so i have to split it manually
        images_color = [color for colors in images_color for color in colors.split(',')]
        images_color_code = [code for codes in images_color_code for code in codes.split(',')]

        # if still not matching - error
        if len(image_paths) != len(images_color) or len(image_paths) != len(images_color_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Mismatch in the number of images and metadata")
    # create image metadata
    image_metadata = await create_image_metadata(image_paths=image_paths, images_color=images_color,
                                                 images_color_code=images_color_code)

    new_product = await ProductCRUDService(session).create_product_item(CreateProduct(name=name,
                                                                                      description=description,
                                                                                      category=category,
                                                                                      brand=brand,
                                                                                      images=image_metadata,
                                                                                      quantity=int(quantity),
                                                                                      price=float(price),
                                                                                      in_stock=in_stock))
    return new_product


@product_routes.get("/get_all_products", status_code=status.HTTP_200_OK)
async def get_all_products(session: AsyncSession = Depends(get_db_session)):
    all_products = await ProductCRUDService(session).get_all_products()
    return all_products


@product_routes.post("/create_product_review", status_code=status.HTTP_201_CREATED)
async def create_product_review(current_user: Annotated[dict, Depends(get_current_user)],
                                product_review: CreateProductReview,
                                session: AsyncSession = Depends(get_db_session)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    product_review = await ProductCRUDService(session).create_product_review(
        CreateProductReview(product_id=product_review.product_id,
                            comment=product_review.comment,
                            user_id=current_user['id'],
                            rating=product_review.rating))
    return product_review
