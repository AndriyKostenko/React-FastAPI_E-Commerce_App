from typing import List, Annotated, Dict, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
import os
from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.product_service import ProductCRUDService
from src.schemas.product_schemas import CreateProduct
from src.utils.image_metadata import create_image_metadata
from src.utils.image_pathes import create_image_paths
from src.errors.database_errors import DatabaseError

product_routes = APIRouter(
    tags=["product"]
)


@product_routes.post("/products", status_code=status.HTTP_201_CREATED)
async def create_new_product(current_user: Annotated[dict, Depends(get_current_user)],
                             name: str = Form(...),
                             description: str = Form(...),
                             category_id: str = Form(...),
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

    if isinstance(in_stock, str):
        if in_stock.lower() == "true":
            in_stock = True
        else:
            in_stock = False


    # create image paths
    image_paths = await create_image_paths(images=images)

    # Validating that the lengths of the lists match....number of pict = color = color codes (only for inputs from
    # Swagger)
    if len(image_paths) != len(images_color) or len(image_paths) != len(images_color_code):
        # TODO : so, i have to get data from Form from client and its separating data correctly in the list...but
        #  when i do it from Swagger, all image_colors and image_color_codes are passed as a single string..so i have
        #  to split it

        # data from Swagger will be passed as a single string with comas, so i have to split it manually
        images_color = [color for colors in images_color for color in colors.split(',')]
        images_color_code = [code for codes in images_color_code for code in codes.split(',')]

        # if still not matching - error
        if len(image_paths) != len(images_color) or len(image_paths) != len(images_color_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Mismatch in the number of images and metadata")
    # create image metadata
    image_metadata = await create_image_metadata(image_paths=image_paths, images_color=images_color,
                                                 images_color_code=images_color_code)

    # create product
    new_product = await ProductCRUDService(session).create_product_item(CreateProduct(name=name,
                                                                                      description=description,
                                                                                      category_id=category_id,
                                                                                      brand=brand,
                                                                                      images=image_metadata,
                                                                                      quantity=int(quantity),
                                                                                      price=float(price),
                                                                                      in_stock=in_stock))

    return new_product


@product_routes.get("/products", status_code=status.HTTP_200_OK)
async def get_all_products(category: Optional[str] = None,
                           searchTerm: Optional[str] = None,
                           session: AsyncSession = Depends(get_db_session)):
    products = await ProductCRUDService(session).get_all_products(category=category, searchTerm=searchTerm)
    return products if products else HTTPException(status_code=404, detail="No products found")


@product_routes.get("/products/{product_id}", status_code=status.HTTP_200_OK)
async def get_product_by_id(product_id: str,
                            session: AsyncSession = Depends(get_db_session)):
    try:
        product = await ProductCRUDService(session).get_product_by_id(product_id=product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except DatabaseError as error:
        raise HTTPException(status_code=404, detail=str(error))

@product_routes.get("/products/{name}", status_code=status.HTTP_200_OK)
async def get_product_by_name(name: str,
                              session: AsyncSession = Depends(get_db_session)):
    product = await ProductCRUDService(session).get_product_by_name(name=name)
    return product if product else HTTPException(status_code=404, detail="Product not found")


@product_routes.put("/products/{product_id}", status_code=status.HTTP_200_OK)
async def update_product_availability(product_id: str,
                                      in_stock: bool,
                                      session: AsyncSession = Depends(get_db_session)):
    # fastapi automatically getting query parameter 'in_stock' from the url\
    product = await ProductCRUDService(session).update_product_availability(product_id=product_id, in_stock=in_stock)
    return product if product else HTTPException(status_code=404, detail="Product not found")


@product_routes.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str,
                         current_user: Annotated[dict, Depends(get_current_user)],
                         session: AsyncSession = Depends(get_db_session)):
    if current_user["user_role"] != "admin" or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    deleted_product = await ProductCRUDService(session).delete_product(product_id=product_id)
    if not deleted_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

