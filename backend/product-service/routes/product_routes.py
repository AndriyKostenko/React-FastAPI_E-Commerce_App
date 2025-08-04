from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, status, HTTPException, Form, UploadFile, File

from dependencies.dependencies import product_service_dependency
from schemas.product_schemas import ImageType, ProductBase, ProductSchema, CreateProduct
from utils.image_pathes import create_image_paths
from utils.image_metadata import create_image_metadata
from shared.customized_json_response import JSONResponse
from shared.shared_instances import product_service_redis_manager


product_routes = APIRouter(
    tags=["product"]
)


@product_routes.post("/products",  
                     response_model=ProductSchema,
                     response_description="New product created")
@product_service_redis_manager.cached(ttl=60)
@product_service_redis_manager.ratelimiter(times=5, seconds=120)
async def create_new_product(product_service: product_service_dependency,
                             name: str = Form(..., min_length=3, max_length=50),
                             description: str = Form(..., min_length=10, max_length=500),
                             category_id: UUID = Form(...),
                             brand: str = Form(...),
                             quantity: int = Form(..., ge=0, le=100),
                             price: Decimal = Form(..., ge=0, le=100),
                             in_stock: bool = Form(...),
                             images_color: List[str] = Form(...),
                             images_color_code: List[str] = Form(...),
                             images: List[UploadFile] = File(...),
                             ):

    # convert in_stock to boolean coz it will be passed as a string from client
    if isinstance(in_stock, str):
        if in_stock.lower() == "true":
            in_stock = True
        else:
            in_stock = False
    
    # creating image pasths
    image_paths = await create_image_paths(images=images)

    # processing color and color code lists
    colors = [color.strip() for colors in images_color for color in colors.split(',')]
    color_codes = [code.strip() for codes in images_color_code for code in codes.split(',')]
    
    print(f"Colors: {colors}, Color Codes: {color_codes}, Image Paths: {image_paths}")

    # validating equal emaount of images and metadata
    if len(image_paths) != len(colors) or len(image_paths) != len(color_codes) or len(colors) != len(color_codes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Number of images: {len(image_paths)} must match number of colors: {len(colors)} and color codes: {len(color_codes)}")

    # Validate minimum length for colors and codes
    if any(len(color) < 3 for color in images_color) or any(len(code) < 3 for code in images_color_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Colors and color codes must be at least 3 characters long"
        )
    
    image_data = [
        (ImageType(image_url=path, 
                   image_color=color,
                   image_color_code=code))
        for color, code, path in zip(colors, color_codes, image_paths)
    ]

    product_data = CreateProduct(name=name.lower(),
                                description=description,
                                category_id=category_id,
                                brand=brand.lower(),
                                images=image_data,
                                quantity=quantity,
                                price=price,
                                in_stock=in_stock)

    created_product =  await product_service.create_product_item(product_data=product_data)
    return JSONResponse(
        content=created_product,
        status_code=status.HTTP_201_CREATED
    )


@product_routes.get("/products", 
                    response_model=list[ProductBase],
                    response_description="All products")
@product_service_redis_manager.cached(ttl=60)
@product_service_redis_manager.ratelimiter(times=5, seconds=120)
async def get_all_products(product_service: product_service_dependency,
                           category: Optional[str] = None,
                           searchTerm: Optional[str] = None,
                           page: int = 1,
                           page_size: int = 10,
                           ):
    products = await product_service.get_all_products(category=category,
                                                      searchTerm=searchTerm,
                                                      page_size=page_size,
                                                      page=page)
    return JSONResponse(
        content=products,
        status_code=status.HTTP_200_OK
    )
        
@product_routes.get("/products/with_relations", 
                    status_code=status.HTTP_200_OK,
                    response_model=list[ProductSchema],
                    response_description="All products with relations")
async def get_all_products_with_relations(product_service: product_service_dependency,
                                          category: Optional[str] = None,
                                          searchTerm: Optional[str] = None,
                                          page: int = 1,
                                          page_size: int = 10,
                                          ) -> list[ProductSchema]:
    return await product_service.get_all_products_with_relations(category=category,
                                                                  searchTerm=searchTerm,
                                                                  page_size=page_size,
                                                                  page=page)


@product_routes.get("/products/id/{product_id}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductBase,
                    response_description="Product by ID")
async def get_product_by_id(product_id: UUID,
                            product_service: product_service_dependency) -> ProductBase:
    return await product_service.get_product_by_id(product_id=product_id)
    

@product_routes.get("/products/name/{product_name}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductBase,
                    response_description="Product by name")
async def get_product_by_name(product_name: str,
                              product_service: product_service_dependency) -> ProductBase:
    return await product_service.get_product_by_name(name=product_name.lower())


@product_routes.patch("/products/{product_id}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductBase,
                    response_description="Product availability updated")
async def update_product_availability(product_id: UUID,
                                      in_stock: bool,
                                      product_service: product_service_dependency) -> ProductBase:
    return await product_service.update_product_availability(product_id=product_id, in_stock=in_stock)

        
    
@product_routes.delete("/products/{product_id}", 
                       status_code=status.HTTP_204_NO_CONTENT,
                       response_description="Product deleted")
async def delete_product(product_id: UUID,
                         product_service: product_service_dependency) -> None:
    return await product_service.delete_product(product_id=product_id)


