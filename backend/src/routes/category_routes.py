from typing import Annotated, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.category_service import CategoryCRUDService
from src.utils.image_pathes import create_image_paths


category_routes = APIRouter(
    tags=["categories"]
)

@category_routes.get("/categories", status_code=status.HTTP_200_OK)
async def get_all_categories(session: AsyncSession = Depends(get_db_session)):
    return await CategoryCRUDService(session=session).get_all_categories()




@category_routes.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(current_user: Annotated[dict, Depends(get_current_user)],
                          session: AsyncSession = Depends(get_db_session),
                          name: str = Form(...),
                          image: UploadFile = File(...)):
    if current_user["user_role"] != "admin" or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Create image paths
    image_paths = await create_image_paths(images=[image])

    # Create category with the image URL

    new_category = await CategoryCRUDService(session=session).create_category(name=name, image_url=image_paths[0])
    return new_category

@category_routes.get("/categories/{category_id}", status_code=status.HTTP_200_OK)
async def get_category_by_id(category_id: int,
                             current_user: Annotated[dict, Depends(get_current_user)],
                             session: AsyncSession = Depends(get_db_session)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return await CategoryCRUDService(session=session).get_category_by_id(category_id=category_id)

@category_routes.put("/categories/{category_id}", status_code=status.HTTP_200_OK)
async def update_category(category_id: str,
                          current_user: Annotated[dict, Depends(get_current_user)],
                          session: AsyncSession = Depends(get_db_session),
                          name: Optional[str] = Form(None),
                          image: Optional[UploadFile] = File(None)):
        if current_user["user_role"] != "admin" or current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

        # Create image paths if an image is provided
        image_url = None
        if image:
            image_paths = await create_image_paths(images=[image])
            image_url = image_paths[0]

        # Update category with the image URL
        updated_category = await CategoryCRUDService(session=session).update_category(id=category_id, name=name, image_url=image_url)
        return updated_category