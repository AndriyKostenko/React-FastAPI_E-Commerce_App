from fastapi import HTTPException, status, APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.user_service import UserCRUDService


admin_routes = APIRouter(tags=['admin'])


@admin_routes.get('/users', summary='Get all users from DB', status_code=status.HTTP_200_OK)
async def read_users(current_user: Annotated[dict, Depends(get_current_user)],
                     session: AsyncSession = Depends(get_db_session)):

    if current_user is None or current_user.get('user_role') != 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    db_users = await UserCRUDService(session).get_all_users()
    return db_users

