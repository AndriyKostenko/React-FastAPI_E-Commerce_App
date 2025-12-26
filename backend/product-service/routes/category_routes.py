from typing import Annotated, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from shared.customized_json_response import JSONResponse
from shared.shared_instances import product_service_redis_manager, settings

from dependencies.dependencies import category_service_dependency
from models.category_models import ProductCategory
from schemas.category_schema import (
    CategoriesFilterParams,
    CategorySchema,
    CreateCategory,
    UpdateCategory,
)

category_routes = APIRouter(tags=["categories"])


# JSON endpoint for AdminJS and API clients
@category_routes.post(
    "/categories", response_model=CategorySchema, summary="Create category (JSON)"
)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_category_json(
    request: Request,
    category_service: category_service_dependency,
    category_data: CreateCategory,
) -> JSONResponse:
    """
    Create a new category using JSON payload.
    Used by AdminJS and API clients.
    """
    new_category = await category_service.create_category(category_data=category_data)
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="categories"
    )
    return JSONResponse(content=new_category, status_code=status.HTTP_201_CREATED)


# FormData endpoint for file uploads (frontend with image)
@category_routes.post(
    "/categories/upload",
    response_model=CategorySchema,
    summary="Create category with image (FormData)",
)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_category_with_image(
    request: Request,
    category_service: category_service_dependency,
    name: str = Form(...),
    image: UploadFile = File(...),
) -> JSONResponse:
    """
    Create a new category with optional image upload.
    Used by frontend forms that need to upload files.
    """
    category_data = CreateCategory(name=name, image_url=None)
    new_category = await category_service.create_category(
        category_data=category_data, image=image
    )
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="categories"
    )
    return JSONResponse(content=new_category, status_code=status.HTTP_201_CREATED)


@category_routes.get("/categories", response_model=list[CategorySchema])
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_all_categories(
    request: Request,
    category_service: category_service_dependency,
    filters_query: Annotated[CategoriesFilterParams, Query()],
) -> JSONResponse:
    categories = await category_service.get_all_categories()
    return JSONResponse(content=categories, status_code=status.HTTP_200_OK)


@category_routes.get("/categories/{category_id}", response_model=CategorySchema)
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_category_by_id(
    request: Request, category_id: UUID, category_service: category_service_dependency
) -> JSONResponse:
    category = await category_service.get_category_by_id(category_id=category_id)
    return JSONResponse(content=category, status_code=status.HTTP_200_OK)


@category_routes.patch("/categories/{category_id}", response_model=CategorySchema)
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
async def update_category_by_id(
    request: Request,
    category_id: UUID,
    category_service: category_service_dependency,
    name: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
) -> JSONResponse:
    updated_category = await category_service.update_category(
        category_id=category_id, name=name, image=image
    )
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="categories"
    )
    return JSONResponse(content=updated_category, status_code=status.HTTP_200_OK)


@category_routes.delete(
    "/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT
)
@product_service_redis_manager.ratelimiter(times=5, seconds=60)
async def delete_category_by_id(
    request: Request, category_id: UUID, category_service: category_service_dependency
) -> None:
    await category_service.delete_category(category_id=category_id)
    # Clear ALL category-related cache
    await product_service_redis_manager.clear_cache_namespace(
        request=request, namespace="categories"
    )
    return


@category_routes.get("/admin/schema/categories", summary="Schema for AdminJS")
async def get_product_schema_for_admin_js(request: Request):
    return JSONResponse(
        content={"fields": ProductCategory.get_admin_schema()},
        status_code=status.HTTP_200_OK,
    )
