from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request, status, Form, UploadFile, File

from dependencies.dependencies import category_service_dependency

from schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory
from shared.shared_instances import product_service_redis_manager, settings
from shared.customized_json_response import JSONResponse
from models.category_models import ProductCategory



category_routes = APIRouter(
    tags=["categories"]
)


@category_routes.post("/categories", 
                      response_model=CategorySchema)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_category(request: Request,
                          category_service: category_service_dependency,
                          name: str = Form(...),
                          image: UploadFile = File(...)) -> JSONResponse:
    new_category =  await category_service.create_category(name=name, image=image)
    # Clear ALL category-related cache
    await product_service_redis_manager.clear_cache_namespace(request=request, namespace="categories")
    return JSONResponse(
        content=new_category,
        status_code=status.HTTP_201_CREATED
    )


@category_routes.get("/categories",
                     response_model=list[CategorySchema])
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_all_categories(request: Request,
                             category_service: category_service_dependency) -> JSONResponse:
    categories = await category_service.get_all_categories()
    return JSONResponse(
        content=categories,
        status_code=status.HTTP_200_OK
    )


@category_routes.get("/categories/id/{category_id}", 
                     response_model=CategorySchema)
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_category_by_id(request: Request,
                             category_id: UUID,
                             category_service: category_service_dependency) -> JSONResponse:
    category = await category_service.get_category_by_id(category_id=category_id)
    return JSONResponse(
        content=category,
        status_code=status.HTTP_200_OK
    )


@category_routes.get("/categories/name/{category_name}", 
                     response_model=CategorySchema)
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_category_by_name(request: Request,
                               category_name: str,
                               category_service: category_service_dependency) -> JSONResponse:
    category = await category_service.get_category_by_name(name=category_name)
    return JSONResponse(
        content=category,
        status_code=status.HTTP_200_OK
    )


@category_routes.patch("/categories/id/{category_id}", 
                     response_model=CategorySchema)
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
async def update_category_by_id(request: Request,
                                category_id: UUID,
                                category_service: category_service_dependency,
                                name: Optional[str] = Form(None),
                                image: Optional[UploadFile] = File(None)) -> JSONResponse:
        updated_category = await category_service.update_category(category_id=category_id, 
                                                                  name=name, 
                                                                  image=image)
        # Clear ALL category-related cache
        await product_service_redis_manager.clear_cache_namespace(request=request, namespace="categories")
        
        return JSONResponse(
            content=updated_category,
            status_code=status.HTTP_200_OK
        )
        
@category_routes.delete("/categories/id/{category_id}",
                        status_code=status.HTTP_204_NO_CONTENT)
@product_service_redis_manager.ratelimiter(times=5, seconds=60)
async def delete_category_by_id(request: Request,
                                category_id: UUID,
                                category_service: category_service_dependency) -> None:
    await category_service.delete_category(category_id=category_id)
    # Clear ALL category-related cache
    await product_service_redis_manager.clear_cache_namespace(request=request, namespace="categories")
    return


@category_routes.get("/admin/schema/categories", summary="Schema for AdminJS")
async def get_product_schema_for_admin_js(request: Request):
    return JSONResponse(content={"fields": ProductCategory.get_admin_schema()},
                        status_code=status.HTTP_200_OK)