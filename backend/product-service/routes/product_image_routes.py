from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status, Form, UploadFile, File

from schemas.product_image_schema import ProductImageSchema, ImageType
from dependencies.dependencies import product_image_service_dependency
from utils.image_pathes import create_image_paths
from shared.shared_instances import product_service_redis_manager, settings
from shared.customized_json_response import JSONResponse


product_images_routes = APIRouter(tags=["product_images"])


@product_images_routes.post("/{product_id}/images", 
                            response_model=list[ProductImageSchema],
                            response_description="Add images to product")
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def add_product_images(request: Request,
                            image_service: product_image_service_dependency,
                            product_id: UUID,
                            images: List[UploadFile] = File(...),
                            colors: List[str] = Form(...),
                            color_codes: List[str] = Form(...)) -> JSONResponse:
    # Create image paths from uploaded files
    image_paths = await create_image_paths(images=images)

    # Process colors and color codes
    processed_colors = []
    processed_color_codes = []
    
    for color_list in colors:
        processed_colors.extend([color.strip() for color in color_list.split(',')])
    
    for code_list in color_codes:
        processed_color_codes.extend([code.strip() for code in code_list.split(',')])

    # Validate equal amount of images and metadata
    if len(image_paths) != len(processed_colors) or len(image_paths) != len(processed_color_codes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Number of images: {len(image_paths)} must match number of colors: {len(processed_colors)} and color codes: {len(processed_color_codes)}"
        )

    # Validate minimum length for colors and codes
    if any(len(color) < 3 for color in processed_colors) or any(len(code) < 3 for code in processed_color_codes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Colors and color codes must be at least 3 characters long"
        )
    
    # Create image data
    image_data = [
        ImageType(
            image_url=path, 
            image_color=color,
            image_color_code=code
        )
        for color, code, path in zip(processed_colors, processed_color_codes, image_paths)
    ]
    
    new_product_images = await image_service.create_product_images(product_id, image_data)
    
    # Clear ALL image-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/images*"
    )
    
    return JSONResponse(
        content=new_product_images,
        status_code=status.HTTP_201_CREATED
    )


@product_images_routes.get("/{product_id}/images",
                           response_model=List[ProductImageSchema],
                           response_description="Get all images for a product")
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_product_images(request: Request,
                             product_id: UUID,
                             image_service: product_image_service_dependency) -> JSONResponse:
    product_images = await image_service.get_product_images(product_id)
    return JSONResponse(
        content=product_images,
        status_code=status.HTTP_200_OK
    )


@product_images_routes.get("/images/{image_id}",
                           response_model=ProductImageSchema,
                           response_description="Get image by ID")
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_image_by_id(request: Request,
                          image_id: UUID,
                          image_service: product_image_service_dependency) -> JSONResponse:
    image = await image_service.get_image_by_id(image_id)
    return JSONResponse(
        content=image,
        status_code=status.HTTP_200_OK
    )


@product_images_routes.put("/{product_id}/images", 
                           response_model=List[ProductImageSchema],
                           response_description="Replace all product images")
@product_service_redis_manager.ratelimiter(times=5, seconds=60)
async def replace_product_images(request: Request,
                                 image_service: product_image_service_dependency,
                                 product_id: UUID,
                                 images: List[UploadFile] = File(...),
                                 colors: List[str] = Form(...),
                                 color_codes: List[str] = Form(...)) -> JSONResponse:
    # Create image paths from uploaded files
    image_paths = await create_image_paths(images=images)

    # Process colors and color codes
    processed_colors = []
    processed_color_codes = []
    
    for color_list in colors:
        processed_colors.extend([color.strip() for color in color_list.split(',')])
    
    for code_list in color_codes:
        processed_color_codes.extend([code.strip() for code in code_list.split(',')])

    # Validate equal amount of images and metadata
    if len(image_paths) != len(processed_colors) or len(image_paths) != len(processed_color_codes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Number of images: {len(image_paths)} must match number of colors: {len(processed_colors)} and color codes: {len(processed_color_codes)}"
        )

    # Validate minimum length for colors and codes
    if any(len(color) < 3 for color in processed_colors) or any(len(code) < 3 for code in processed_color_codes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Colors and color codes must be at least 3 characters long"
        )
    
    # Create image data
    image_data = [
        ImageType(
            image_url=path, 
            image_color=color,
            image_color_code=code
        )
        for color, code, path in zip(processed_colors, processed_color_codes, image_paths)
    ]
    
    updated_images = await image_service.replace_product_images(product_id, image_data)
    
    # Clear ALL image-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/images*"
    )
    
    return JSONResponse(
        content=updated_images,
        status_code=status.HTTP_200_OK
    )


@product_images_routes.patch("/images/{image_id}",
                             response_model=ProductImageSchema,
                             response_description="Update single image")
@product_service_redis_manager.ratelimiter(times=20, seconds=60)
async def update_product_image(request: Request,
                               image_id: UUID,
                               image_service: product_image_service_dependency,
                               image: UploadFile = File(None),
                               color: str = Form(None),
                               color_code: str = Form(None)) -> JSONResponse:
    image_url = None
    if image:
        image_paths = await create_image_paths(images=[image])
        image_url = image_paths[0]
    
    updated_image = await image_service.update_product_image(
        image_id=image_id,
        image_url=image_url,
        color=color,
        color_code=color_code
    )
    # Clear ALL image-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/images*"
    )

    return JSONResponse(
        content=updated_image,
        status_code=status.HTTP_200_OK
    )


@product_images_routes.delete("/images/{image_id}",
                              response_description="Delete image by ID")
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def delete_product_image(request: Request,
                               image_id: UUID,
                               image_service: product_image_service_dependency) -> JSONResponse:
    await image_service.delete_product_image(image_id)
    
    # Clear ALL image-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/images*"
    )
    
    return JSONResponse(
        content=None,
        status_code=status.HTTP_204_NO_CONTENT
    )