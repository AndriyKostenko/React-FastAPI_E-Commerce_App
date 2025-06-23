from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, status, HTTPException, Form, UploadFile, File

from dependencies import product_crud_dependency
from schemas.product_schemas import ProductSchema, CreateProduct
from utils.image_pathes import create_image_paths
from utils.image_metadata import create_image_metadata


product_routes = APIRouter(
    tags=["product"]
)


@product_routes.post("/products", 
                     status_code=status.HTTP_201_CREATED, 
                     response_model=ProductSchema,
                     response_description="New product created")
async def create_new_product(product_crud_service: product_crud_dependency,
                             name: str = Form(..., min_length=3, max_length=50),
                             description: str = Form(..., min_length=10, max_length=500),
                             category_id: str = Form(...),
                             brand: str = Form(...),
                             quantity: int = Form(..., ge=0, le=100),
                             price: Decimal = Form(..., ge=0, le=100),
                             in_stock: bool = Form(...),
                             images_color: List[str] = Form(...),
                             images_color_code: List[str] = Form(...),
                             images: List[UploadFile] = File(...),
                             ) -> ProductSchema:

    # convert in_stock to boolean coz it will be passed as a string from client
    if isinstance(in_stock, str):
        if in_stock.lower() == "true":
            in_stock = True
        else:
            in_stock = False
    
    image_paths = await create_image_paths(images=images)

    # Validating that the lengths of the lists match....number of pict = color = color codes (only for inputs from
    # Swagger)
    # TODO : so, i have to get data from Form from client and its separating data correctly in the list...but
    #  when i do it from Swagger, all image_colors and image_color_codes are passed as a single string..so i have
    #  to split it

    # data from Swagger will be passed as a single string with comas, so i have to split it manually
    images_color = [color for colors in images_color for color in colors.split(',')]
    images_color_code = [code for codes in images_color_code for code in codes.split(',')]

    print(f"images_color: {images_color}, images_color_code: {images_color_code}, image_paths: {image_paths}")

    # if not matching - error
    if len(image_paths) != len(images_color) or len(image_paths) != len(images_color_code) or len(images_color) != len(images_color_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Mismatch in the number of images and metadata")
        
    image_metadata = await create_image_metadata(image_paths=image_paths, 
                                                 images_color=images_color,
                                                 images_color_code=images_color_code)

    new_product = await product_crud_service.create_product_item(CreateProduct(name=name,
                                                                               description=description,
                                                                               category_id=category_id,
                                                                               brand=brand,
                                                                               images=image_metadata,
                                                                               quantity=quantity,
                                                                               price=price,
                                                                               in_stock=in_stock))

    return new_product 



@product_routes.get("/products", 
                    status_code=status.HTTP_200_OK,
                    response_model=List[ProductSchema],
                    response_description="All products")
async def get_all_products(product_crud_service: product_crud_dependency,
                           category: Optional[str] = None,
                           searchTerm: Optional[str] = None,
                           page: int = 1,
                           page_size: int = 10,
                           ) -> List[ProductSchema]:
  
    return await product_crud_service.get_all_products(category=category,
                                                           searchTerm=searchTerm,
                                                           page_size=page_size,
                                                           page=page)
        



@product_routes.get("/products/{product_id}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductSchema,
                    response_description="Product by ID")
async def get_product_by_id(product_id: UUID,
                            product_crud_service: product_crud_dependency) -> ProductSchema:
    return await product_crud_service.get_product_by_id(product_id=product_id)
    

@product_routes.get("/products/name/{name}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductSchema,
                    response_description="Product by name")
async def get_product_by_name(name: str,
                              product_crud_service: product_crud_dependency) -> ProductSchema:
    return await product_crud_service.get_product_by_name(name=name)

 

@product_routes.put("/products/{product_id}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductSchema,
                    response_description="Product availability updated",
                    responses={
                        200: {"description": "Product availability updated"},
                        404: {"description": "Product not found"},
                        500: {"description": "Internal server error"}})
async def update_product_availability(product_id: UUID,
                                      in_stock: bool,
                                      product_crud_service: product_crud_dependency) -> ProductSchema:
    return await product_crud_service.update_product_availability(product_id=product_id, in_stock=in_stock)

        
    
@product_routes.delete("/products/{product_id}", 
                       status_code=status.HTTP_204_NO_CONTENT,
                       response_description="Product deleted")
async def delete_product(product_id: UUID,
                         product_crud_service: product_crud_dependency
                         ) -> None:
    return await product_crud_service.delete_product(product_id=product_id)


