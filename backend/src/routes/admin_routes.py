from fastapi import HTTPException, status, APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List
from src.dependencies.dependencies import get_db_session
from src.schemas.user_schemas import UserUpdate, UserInfo
from src.security.authentication import auth_manager
from src.dependencies.dependencies import get_user_service
from src.routes.user_routes import UserCRUDService
from src.dependencies.dependencies import require_admin

admin_routes = APIRouter(tags=['admin'],
                         prefix='/admin',
                         dependencies=[Depends(require_admin)]) # dependency function of automatically applying admin check to all routes


@admin_routes.get('/users',
                  summary='Get all users from DB',
                  status_code=status.HTTP_200_OK,
                  response_model=List[UserInfo])
async def get_all_users(user_service: UserCRUDService = Depends(get_user_service)):
    return await user_service.get_all_users()



@admin_routes.get('/users/{user_id}', summary='Get user by ID', status_code=status.HTTP_200_OK)
async def get_user_by_id(user_id: str,
                         current_user: Annotated[dict, Depends(auth_manager.get_current_user_from_token)],
                         session: AsyncSession = Depends(get_db_session)):
    if current_user is None or current_user.user_role != 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    db_user = await UserCRUDService(session).get_user_by_id(user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return db_user


@admin_routes.put('/users/{user_id}', summary='Update user by ID', status_code=status.HTTP_200_OK)
async def update_user_by_id(user_id: str,
                            user_update_data: UserUpdate,
                            current_user: Annotated[dict, Depends(auth_manager.get_current_user_from_token)],
                            session: AsyncSession = Depends(get_db_session)):
    if current_user is None or current_user.user_role != 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    db_user = await UserCRUDService(session).get_user_by_id(user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    
    updated_user = await UserCRUDService(session).update_user_by_id(user_id=user_id, user_update_data=user_update_data)
    
    await invalidate_cache('users', user_id)  # Invalidate cache for the updated user
    
    return updated_user


@admin_routes.delete('/users/{user_id}', summary='Delete user by ID', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(user_id: int,
                            current_user: Annotated[dict, Depends(auth_manager.get_current_user_from_token)],
                            session: AsyncSession = Depends(get_db_session)):
    if current_user is None or current_user.user_role != 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    db_user = await UserCRUDService(session).get_user_by_id(user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    await UserCRUDService(session).delete_user_by_id(user_id=user_id)
    return {'message': 'User successfully deleted'}
