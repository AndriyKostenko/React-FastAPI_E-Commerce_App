from typing import Annotated, List
from urllib import response
from uuid import UUID

from fastapi import HTTPException, status, APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.dependencies import user_crud_dependency
from schemas.user_schemas import UserBasicUpdate, UserUpdate, UserInfo
from authentication import auth_manager

from dependencies.dependencies import require_admin

admin_routes = APIRouter(tags=['admin'],
                         prefix='/admin',
                         dependencies=[Depends(require_admin)]) # dependency function of automatically applying admin check to all routes


@admin_routes.get('/users',
                  summary='Get all users from DB',
                  status_code=status.HTTP_200_OK,
                  response_model=list[UserInfo])
async def get_all_users(user_service: user_crud_dependency) -> list[UserInfo]:
    return await user_service.get_all_users() 



@admin_routes.put('/users/{user_id}',
                  response_model=UserInfo, 
                  summary='Update user by ID', 
                  status_code=status.HTTP_200_OK)
async def update_user_by_id(user_id: UUID,
                            user_update_data: UserBasicUpdate,
                            user_service: user_crud_dependency) -> UserInfo:
    return await user_service.update_user_basic_info(user_id=user_id, update_data=user_update_data)


@admin_routes.delete('/users/{user_id}',
                     summary='Delete user by ID', 
                     status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(user_id: UUID,
                            user_service: user_crud_dependency):
    return await user_service.delete_user_by_id(user_id=user_id)
