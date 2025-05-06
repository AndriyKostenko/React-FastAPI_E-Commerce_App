from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.service.user_service import UserCRUDService
from src.db.db_setup import database_session_manager
from typing import AsyncGenerator


# dependency that will be used to get the database session from the request
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Providing a transactional scope around for each series (request) of operations with database."""
    async with database_session_manager.session() as session:
        yield session


# dependency function that provides an instance of UserCRUDService
def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserCRUDService:
    return UserCRUDService(session=session)


