from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request, status, Form, UploadFile, File

from dependencies.dependencies import category_service_dependency
from utils.image_pathes import create_image_paths
from schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory
from shared.shared_instances import product_service_redis_manager, settings
from shared.customized_json_response import JSONResponse


category_routes = APIRouter(
    tags=["categories"]
)


@category_routes.post("/categories", 
                      response_model=CategorySchema)
@product_service_redis_manager.cached(ttl=30)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_category(request: Request,
                          category_service: category_service_dependency,
                          name: str = Form(...),
                          image: UploadFile = File(...)) -> JSONResponse:
    # Create image paths
    image_paths = await create_image_paths(images=[image])
    new_category =  await category_service.create_category(category_data=CreateCategory(
                                                                            name=name.lower(), 
                                                                            image_url=image_paths[0]))
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


@category_routes.put("/categories/{category_id}", 
                     response_model=CategorySchema)
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
async def update_category(request: Request,
                          category_id: UUID,
                          category_service: category_service_dependency,
                          name: Optional[str] = Form(None),
                          image: Optional[UploadFile] = File(None)) -> JSONResponse:
        image_url = None
        if image:
            image_paths = await create_image_paths(images=[image])
            image_url = image_paths[0]
            
        updated_category = await category_service.update_category(
            category_id=category_id, 
            data=UpdateCategory(name=name.lower() if name else None, 
                                image_url=image_url))
            
        # Clear ALL category-related cache
        await product_service_redis_manager.clear_cache_namespace(request=request, namespace="categories")
        
        return JSONResponse(
            content=updated_category,
            status_code=status.HTTP_200_OK
        )
        
@category_routes.delete("/categories/id/{category_id}")
@product_service_redis_manager.ratelimiter(times=5, seconds=60)
async def delete_category_by_id(request: Request,
                                category_id: UUID,
                                category_service: category_service_dependency) -> JSONResponse:
    await category_service.delete_category(category_id=category_id)
    # Clear ALL category-related cache
    await product_service_redis_manager.clear_cache_namespace(request=request, namespace="categories")
    return JSONResponse(
        content=None,
        status_code=status.HTTP_204_NO_CONTENT
    )