from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse

from dependencies.dependencies import (
    image_generation_service_dependency,
    product_image_service_dependency,
    user_context_resolver_dependency,
)
from exceptions.image_generation_exceptions import (
    ImageGenerationLimitExceededError,
)
from models.product_image_models import ProductImage
from shared.schemas.image_generation_schema import (
    GenerateImageRequest,
    ImageGenerationJobSubmitResponse,
    ImageGenerationJobStatusResponse,
    ImageJobStatus,
)
from shared.schemas.product_image_schema import ProductImageSchema
from tasks.image_tasks import generate_image_task


product_images_routes = APIRouter(tags=["product_images"])


@product_images_routes.post(
    "/images/generations",
    response_model=ImageGenerationJobSubmitResponse,
    response_description="Submit image generation job",
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_image(
    request: Request,
    response: Response,
    image_generation_service: image_generation_service_dependency,
    user_context_resolver: user_context_resolver_dependency,
    generation_data: GenerateImageRequest,
) -> ImageGenerationJobSubmitResponse | JSONResponse:
    # Resolve user context (authenticated user or guest with quota tracking)
    context = await user_context_resolver.resolve(request)
    job_id = str(uuid4())
    try:
        remaining_generations = await image_generation_service.submit_job(
            job_id=job_id,
            prompt=generation_data.prompt,
            style=generation_data.style,
            is_guest_user=context.is_guest_user,
            guest_id=context.guest_id,
            user_id=context.user_id,
        )
    except ImageGenerationLimitExceededError as exc:
        # Return a JSONResponse directly so we can attach Set-Cookie
        resp = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )
        if context.cookie_kwargs:
            resp.set_cookie(**{**context.cookie_kwargs, "value": context.new_guest_id})
        return resp

    await generate_image_task.kiq(
        job_id,
        generation_data.prompt,
        generation_data.style,
        generation_data.remove_background,
    )

    if context.cookie_kwargs:
        response.set_cookie(**{**context.cookie_kwargs, "value": context.new_guest_id})

    # Point the client at the status-poll endpoint
    response.headers["Location"] = f"{request.url.path}/{job_id}/status"

    guest_limit = (
        image_generation_service.settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT
        if context.is_guest_user
        else image_generation_service.settings.PRODUCT_IMAGE_REGISTERED_GENERATION_LIMIT
    )

    return ImageGenerationJobSubmitResponse(
        job_id=job_id,
        status=ImageJobStatus.pending,
        remaining_generations=remaining_generations,
        guest_limit=guest_limit,
    )


@product_images_routes.get(
    "/images/generations/{job_id}/status",
    response_model=ImageGenerationJobStatusResponse,
    response_description="Poll background image generation job status",
    status_code=status.HTTP_200_OK,
)
async def get_generation_job_status(
    request: Request,
    job_id: str,
    image_generation_service: image_generation_service_dependency,
) -> ImageGenerationJobStatusResponse:
    job_data = await image_generation_service.get_job(job_id)
    return ImageGenerationJobStatusResponse(
        job_id=job_id,
        status=ImageJobStatus(job_data["status"]),
        image_url=job_data.get("image_url"),
        model=job_data.get("model"),
        error=job_data.get("error"),
    )


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
