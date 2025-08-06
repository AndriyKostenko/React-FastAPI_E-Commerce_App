from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Form, UploadFile, File

from schemas.product_image_schema import ProductImageSchema, ImageType
from dependencies.dependencies import product_image_service_dependency
from utils.image_pathes import create_image_paths
from shared.customized_json_response import JSONResponse


product_images_routes = APIRouter(tags=["product_images"])


@product_images_routes.post("/{product_id}/images", 
                            response_model=List[ProductImageSchema])
async def add_product_images(
     image_service: product_image_service_dependency,
    product_id: UUID,
    images: List[UploadFile] = File(..., description="List of image files to upload"),
    colors: List[str] = Form(..., description="Comma-separated colors for each image"),
    color_codes: List[str] = Form(..., description="Comma-separated color codes for each image"),
   
):
    # Create image paths from uploaded files
    image_paths = await create_image_paths(images=images)

    # Process colors and color codes
    processed_colors = []
    processed_color_codes = []
    
    for color_list in colors:
        processed_colors.extend([color.strip() for color in color_list.split(',')])
    
    for code_list in color_codes:
        processed_color_codes.extend([code.strip() for code in code_list.split(',')])
    
    print(f"Colors: {processed_colors}, Color Codes: {processed_color_codes}, Image Paths: {image_paths}")

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
    return JSONResponse(
        content=new_product_images,
        status_code=status.HTTP_201_CREATED
    )

@product_images_routes.get("/{product_id}/images",
                           response_model=List[ProductImageSchema])
async def get_product_images(product_id: UUID,
                             image_service: product_image_service_dependency):
    product_images = await image_service.get_product_images(product_id)
    return JSONResponse(
        content=product_images,
        status_code=status.HTTP_200_OK
    )

@product_images_routes.get("/{product_id}/images/{image_id}",
                           response_model=ProductImageSchema)
async def get_product_image(product_id: UUID,
                            image_id: UUID,
                            image_service: product_image_service_dependency):
    return await image_service.get_image_by_id(image_id)


@product_images_routes.put("/{product_id}/images", 
                           response_model=List[ProductImageSchema])
async def replace_product_images(
    image_service: product_image_service_dependency,
    product_id: UUID,
    images: List[UploadFile] = File(..., description="List of image files to upload"),
    colors: List[str] = Form(..., description="Comma-separated colors for each image"),
    color_codes: List[str] = Form(..., description="Comma-separated color codes for each image"),
):
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
    
    return await image_service.replace_product_images(product_id, image_data)


@product_images_routes.delete("/{product_id}/images/{image_id}")
async def delete_product_image(product_id: UUID,
                                image_id: UUID,
                                image_service: product_image_service_dependency):
    return await image_service.delete_product_image(image_id)