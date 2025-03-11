from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.db_setup import get_db_session
from src.service.user_service import UserCRUDService


# Dependency to get the user service for CRUD operations
def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserCRUDService:
    return UserCRUDService(session=session)
