from typing import List
from uuid import UUID

from fastapi import APIRouter, File, Form, Request, UploadFile, status

from shared.customized_json_response import JSONResponse  # type: ignore
from shared.shared_instances import product_service_redis_manager  # type: ignore
from dependencies.dependencies import product_image_service_dependency
from models.product_image_models import ProductImage
from schemas.product_image_schema import ProductImageSchema

product_images_routes = APIRouter(tags=["product_images"])


@product_images_routes.post(
    "/{product_id}/images",
    response_model=list[ProductImageSchema],
    response_description="Add images to product",
)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def add_product_images(
    request: Request,
    image_service: product_image_service_dependency,
    product_id: UUID,
    images: List[UploadFile] = File(...),
    colors: List[str] = Form(...),
    color_codes: List[str] = Form(...),
) -> JSONResponse:
    new_product_images = await image_service.create_product_images_with_files(
        product_id=product_id,
        images=images,
        colors=colors,
        color_codes=color_codes,
    )
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="product_images"
    )
    return JSONResponse(content=new_product_images, status_code=status.HTTP_201_CREATED)


@product_images_routes.get("/images", response_description="Get all images")
async def get_all_images(
    request: Request, image_service: product_image_service_dependency
) -> JSONResponse:
    images = await image_service.get_images()
    return JSONResponse(content=images, status_code=status.HTTP_200_OK)


@product_images_routes.get(
    "/{product_id}/images",
    response_model=List[ProductImageSchema],
    response_description="Get all images for a product",
)
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_product_images(
    request: Request, product_id: UUID, image_service: product_image_service_dependency
) -> JSONResponse:
    product_images = await image_service.get_product_images(product_id)
    return JSONResponse(content=product_images, status_code=status.HTTP_200_OK)


@product_images_routes.get(
    "/images/{image_id}",
    response_model=ProductImageSchema,
    response_description="Get image by ID",
)
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_image_by_id(
    request: Request, image_id: UUID, image_service: product_image_service_dependency
) -> JSONResponse:
    image = await image_service.get_image_by_id(image_id)
    return JSONResponse(content=image, status_code=status.HTTP_200_OK)


@product_images_routes.put(
    "/{product_id}/images",
    response_model=List[ProductImageSchema],
    response_description="Replace all product images",
)
@product_service_redis_manager.ratelimiter(times=5, seconds=60)
async def replace_product_images(
    request: Request,
    image_service: product_image_service_dependency,
    product_id: UUID,
    images: List[UploadFile] = File(...),
    image_colors: List[str] = Form(...),
    color_codes: List[str] = Form(...),
) -> JSONResponse:
    updated_images = await image_service.replace_product_images(
        product_id=product_id,
        images=images,
        image_colors=image_colors,
        color_codes=color_codes
    )
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="product_images"
    )
    return JSONResponse(content=updated_images, status_code=status.HTTP_200_OK)


@product_images_routes.patch(
    "/images/{image_id}",
    response_model=ProductImageSchema,
    response_description="Update single image",
)
@product_service_redis_manager.ratelimiter(times=20, seconds=60)
async def update_product_image(
    request: Request,
    image_id: UUID,
    image_service: product_image_service_dependency,
    image: UploadFile = File(None),
    image_color: str = Form(None),
    image_color_code: str = Form(None),
) -> JSONResponse:
    updated_image = await image_service.update_product_image_with_file(
        image_id=image_id,
        image=image,
        image_color=image_color,
        image_color_code=image_color_code,
    )
    await product_service_redis_manager.clear_cache_namespace(
        request=request,
        namespace="product_images",
    )
    return JSONResponse(content=updated_image, status_code=status.HTTP_200_OK)


@product_images_routes.delete(
    "/images/{image_id}",
    response_description="Delete image by ID",
    status_code=status.HTTP_204_NO_CONTENT,
)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def delete_product_image(
    request: Request, image_id: UUID, image_service: product_image_service_dependency
) -> JSONResponse:
    await image_service.delete_product_image(image_id)
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="product_images"
    )
    return


@product_images_routes.get("/admin/schema/images", summary="Schema for AdminJS")
async def get_product_image_schema_for_admin_js(request: Request):
    return JSONResponse(
        content={"fields": ProductImage.get_admin_schema()},
        status_code=status.HTTP_200_OK,
    )
