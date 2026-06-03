from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status

from dependencies.dependencies import (
    image_generation_service_dependency,
    product_image_service_dependency,
)
from models.product_image_models import ProductImage
from shared.schemas.image_generation_schema import (
    GenerateImageRequest,
    GenerateImageResponse,
)
from shared.schemas.product_image_schema import ProductImageSchema


product_images_routes = APIRouter(tags=["product_images"])


@product_images_routes.post(
    "/images/generations",
    response_model=GenerateImageResponse,
    response_description="Generate image with OpenRouter",
    status_code=status.HTTP_201_CREATED,
)
async def generate_image(
    request: Request,
    response: Response,
    image_generation_service: image_generation_service_dependency,
    generation_data: GenerateImageRequest,
) -> GenerateImageResponse:
    guest_id = request.cookies.get(image_generation_service.GUEST_QUOTA_COOKIE)

    new_guest_id = None
    if not guest_id:
        new_guest_id = str(uuid4())
        guest_id = new_guest_id

    generated_image = await image_generation_service.generate_image(
        prompt=generation_data.prompt,
        style=generation_data.style,
        is_guest_user=True,
        guest_id=guest_id,
    )

    if new_guest_id:
        response.set_cookie(
            key=image_generation_service.GUEST_QUOTA_COOKIE,
            value=new_guest_id,
            httponly=True,
            secure=image_generation_service.settings.SECURE_COOKIES,
            samesite="lax",
            max_age=image_generation_service.settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS
            * 3600,
        )

    return generated_image


@product_images_routes.post(
    "/{product_id}/images",
    response_model=list[ProductImageSchema],
    response_description="Add images to product",
    status_code=status.HTTP_201_CREATED,
)
async def add_product_images(
    request: Request,
    image_service: product_image_service_dependency,
    product_id: UUID,
    images: list[UploadFile] = File(...),
    colors: list[str] = Form(...),
    color_codes: list[str] = Form(...),
) -> list[ProductImageSchema]:
    new_product_images = await image_service.create_product_images_with_files(
        product_id=product_id,
        images=images,
        colors=colors,
        color_codes=color_codes,
    )
    return new_product_images


@product_images_routes.get(
    "/images",
    response_model=list[ProductImageSchema],
    response_description="Get all images",
    status_code=status.HTTP_200_OK,
)
async def get_all_images(
    request: Request, image_service: product_image_service_dependency
) -> list[ProductImageSchema]:
    images = await image_service.get_images()
    return images


@product_images_routes.get(
    "/{product_id}/images",
    response_model=list[ProductImageSchema],
    response_description="Get all images for a product",
    status_code=status.HTTP_200_OK,
)
async def get_product_images(
    request: Request, product_id: UUID, image_service: product_image_service_dependency
) -> list[ProductImageSchema]:
    product_images = await image_service.get_product_images(product_id)
    return product_images


@product_images_routes.get(
    "/images/{image_id}",
    response_model=ProductImageSchema,
    response_description="Get image by ID",
    status_code=status.HTTP_200_OK,
)
async def get_image_by_id(
    request: Request, image_id: UUID, image_service: product_image_service_dependency
) -> ProductImageSchema:
    image = await image_service.get_image_by_id(image_id)
    return image


@product_images_routes.put(
    "/{product_id}/images",
    response_model=list[ProductImageSchema],
    response_description="Replace all product images",
    status_code=status.HTTP_200_OK,
)
async def replace_product_images(
    request: Request,
    image_service: product_image_service_dependency,
    product_id: UUID,
    images: list[UploadFile] = File(...),
    image_colors: list[str] = Form(...),
    color_codes: list[str] = Form(...),
) -> list[ProductImageSchema]:
    updated_images = await image_service.replace_product_images(
        product_id=product_id,
        images=images,
        image_colors=image_colors,
        color_codes=color_codes
    )
    return updated_images


@product_images_routes.patch(
    "/images/{image_id}",
    response_model=ProductImageSchema,
    response_description="Update single image",
    status_code=status.HTTP_200_OK,
)
async def update_product_image(
    request: Request,
    image_id: UUID,
    image_service: product_image_service_dependency,
    image: UploadFile = File(None),
    image_color: str = Form(None),
    image_color_code: str = Form(None),
) -> ProductImageSchema:
    updated_image = await image_service.update_product_image_with_file(
        image_id=image_id,
        image=image,
        image_color=image_color,
        image_color_code=image_color_code,
    )
    return updated_image


@product_images_routes.delete(
    "/images/{image_id}",
    response_description="Delete image by ID",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_image(
    request: Request, image_id: UUID, image_service: product_image_service_dependency
) -> None:
    await image_service.delete_product_image(image_id)
    return


@product_images_routes.get(
    "/admin/schema/images",
    summary="Schema for AdminJS",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_product_image_schema_for_admin_js(request: Request):
    return {"fields": ProductImage.get_admin_schema()}
