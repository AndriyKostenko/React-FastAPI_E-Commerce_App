from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File

from dependencies import category_crud_dependency
from utils.image_pathes import create_image_paths
from schemas.category_schema import CategorySchema



category_routes = APIRouter(
    tags=["categories"]
)

@category_routes.get("/categories", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def get_all_categories(categories_crud_service: category_crud_dependency):
    return await categories_crud_service.get_all_categories()
   


@category_routes.post("/categories", 
                      status_code=status.HTTP_201_CREATED,
                      response_model=CategorySchema)
async def create_category(categories_crud_service: category_crud_dependency,
                          name: str = Form(...),
                          image: UploadFile = File(...)):
    # Create image paths
    image_paths = await create_image_paths(images=[image])
    # Create category with the image URL
    new_category = await categories_crud_service.create_category(name=name, image_url=image_paths[0])
    return new_category 


@category_routes.get("/categories/id/{category_id}", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def get_category_by_id(category_id: UUID,
                             categories_crud_service: category_crud_dependency):
    return await categories_crud_service.get_category_by_id(category_id=category_id)


@category_routes.get("/categories/name/{category_name}", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def get_category_by_name(category_name: str,
                               categories_crud_service: category_crud_dependency):
    return await categories_crud_service.get_category_by_name(name=category_name)
 

@category_routes.delete("/categories/id/{category_id}", 
                        status_code=status.HTTP_204_NO_CONTENT,
                        )
async def delete_category_by_id(category_id: UUID,
                                categories_crud_service: category_crud_dependency):
    return await categories_crud_service.delete_category(category_id=category_id)
 


@category_routes.put("/categories/{category_id}", 
                     status_code=status.HTTP_200_OK,
                     response_model=CategorySchema)
async def update_category(category_id: UUID,
                          categories_crud_service: category_crud_dependency,
                          name: Optional[str] = Form(None),
                          image: Optional[UploadFile] = File(None)):
        # Create image paths if an image is provided
        image_url = None
        if image:
            image_paths = await create_image_paths(images=[image])
            image_url = image_paths[0]

        # Update category with the image URL
        updated_category = await categories_crud_service.update_category(category_id=category_id, name=name, image_url=image_url)
        return updated_category