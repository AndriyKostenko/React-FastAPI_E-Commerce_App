from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, status, Form, UploadFile, File

from dependencies.dependencies import category_service_dependency
from utils.image_pathes import create_image_paths
from schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory



category_routes = APIRouter(
    tags=["categories"]
)

@category_routes.get("/categories", 
                     status_code=status.HTTP_200_OK,
                     response_model=list[CategorySchema])
async def get_all_categories(category_service: category_service_dependency) -> list[CategorySchema]:
    return await category_service.get_all_categories()
   


@category_routes.post("/categories", 
                      status_code=status.HTTP_201_CREATED,
                      response_model=CategorySchema)
async def create_category(category_service: category_service_dependency,
                          name: str = Form(...),
                          image: UploadFile = File(...)) -> CategorySchema:
    # Create image paths
    image_paths = await create_image_paths(images=[image])
    return await category_service.create_category(category_data=CreateCategory(name=name.lower(), image_url=image_paths[0]))


@category_routes.get("/categories/id/{category_id}", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def get_category_by_id(category_id: UUID,
                             category_service: category_service_dependency) -> CategorySchema:
    return await category_service.get_category_by_id(category_id=category_id)


@category_routes.get("/categories/name/{category_name}", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def get_category_by_name(category_name: str,
                               category_service: category_service_dependency) -> CategorySchema:
    return await category_service.get_category_by_name(name=category_name)
 

@category_routes.delete("/categories/id/{category_id}", 
                        status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_by_id(category_id: UUID,
                                category_service: category_service_dependency) -> None:
    return await category_service.delete_category(category_id=category_id)
 


@category_routes.put("/categories/{category_id}", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def update_category(category_id: UUID,
                          category_service: category_service_dependency,
                          name: Optional[str] = Form(None),
                          image: Optional[UploadFile] = File(None)) -> CategorySchema:
        image_url = None
        if image:
            image_paths = await create_image_paths(images=[image])
            image_url = image_paths[0]
        return await category_service.update_category(category_id=category_id, 
                                                      data=UpdateCategory(name=name.lower() if name else None, 
                                                                          image_url=image_url))