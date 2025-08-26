# from typing import Annotated, List
# from urllib import response
# from uuid import UUID

# from fastapi import HTTPException, status, APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession

# from dependencies.dependencies import user_crud_dependency
# from schemas.user_schemas import UserBasicUpdate, UserUpdate, UserInfo
# from authentication import auth_manager

# from dependencies.dependencies import require_admin

# admin_routes = APIRouter(tags=['admin'],
#                          prefix='/admin',
#                          dependencies=[Depends(require_admin)]) # dependency function of automatically applying admin check to all routes


# @admin_routes.get('/users',
#                   summary='Get all users from DB',
#                   status_code=status.HTTP_200_OK,
#                   response_model=list[UserInfo])
# async def get_all_users(user_service: user_crud_dependency) -> list[UserInfo]:
#     return await user_service.get_all_users() 



