from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)

from dependencies.dependencies import category_service_dependency
from models.category_models import ProductCategory
from shared.schemas.category_schema import (
    CategoriesFilterParams,
    CategorySchema,
    CreateCategory,
    UpdateCategory,
)

category_routes = APIRouter(tags=["categories"])


# JSON endpoint for AdminJS and API clients
@category_routes.post(
    "/categories",
    response_model=CategorySchema,
    summary="Create category (JSON)",
    status_code=status.HTTP_201_CREATED,
)
async def create_category_json(
    request: Request,
    category_service: category_service_dependency,
    category_data: CreateCategory,
) -> CategorySchema:
    """
    Create a new category using JSON payload.
    Used by AdminJS and API clients.
    """
    new_category = await category_service.create_category(category_data=category_data)
    return new_category


# FormData endpoint for file uploads (frontend with image)
@category_routes.post(
    "/categories/upload",
    response_model=CategorySchema,
    summary="Create category with image (FormData)",
    status_code=status.HTTP_201_CREATED,
)
async def create_category_with_image(
    request: Request,
    category_service: category_service_dependency,
    name: str = Form(...),
    image: UploadFile = File(...),
) -> CategorySchema:
    """
    Create a new category with optional image upload.
    Used by frontend forms that need to upload files.
    """
    category_data = CreateCategory(name=name, image_url=None)
    new_category = await category_service.create_category(
        category_data=category_data, image=image
    )
    return new_category


@category_routes.get(
    "/categories",
    response_model=list[CategorySchema],
    status_code=status.HTTP_200_OK,
)
async def get_all_categories(
    request: Request,
    category_service: category_service_dependency,
    filters_query: Annotated[CategoriesFilterParams, Query()],
) -> list[CategorySchema]:
    categories = await category_service.get_all_categories()
    return categories


@category_routes.get(
    "/categories/{category_id}",
    response_model=CategorySchema,
    status_code=status.HTTP_200_OK,
)
async def get_category_by_id(
    request: Request, category_id: UUID, category_service: category_service_dependency
) -> CategorySchema:
    category = await category_service.get_category_by_id(category_id=category_id)
    return category


@category_routes.patch(
    "/categories/{category_id}",
    response_model=CategorySchema,
    status_code=status.HTTP_200_OK,
)
async def update_category_by_id(
    request: Request,
    category_id: UUID,
    category_service: category_service_dependency,
    name: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
) -> CategorySchema:
    updated_category = await category_service.update_category(
        category_id=category_id, name=name, image=image
    )
    return updated_category


@category_routes.delete(
    "/categories/{category_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_category_by_id(
    request: Request, category_id: UUID, category_service: category_service_dependency
) -> None:
    await category_service.delete_category(category_id=category_id)
    return


@category_routes.get(
    "/admin/schema/categories",
    summary="Schema for AdminJS",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_product_schema_for_admin_js(request: Request):
    return {"fields": ProductCategory.get_admin_schema()}
