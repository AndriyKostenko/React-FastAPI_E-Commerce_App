from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserCRUDService
from database import database_session_manager
from authentication import auth_manager
from schemas import CurrentUserInfo
from config import get_settings



"""
FLow Diagram for Database Session Management in FastAPI:

    A[HTTP Request] --> B[FastAPI Router]
    B --> C[get_db_session Dependency]
    C --> D[DatabaseSessionManager.session]
    D --> E[Database Operations]
    E --> F[Commit/Rollback]
    F --> G[Session Cleanup]
    G --> H[HTTP Response]
"""


# dependency that will be used to get the database session from the request
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Providing a transactional scope around for each series (request) of operations with database."""
    async with database_session_manager.session() as session:
        yield session

# dependency function that provides an instance of UserCRUDService
def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserCRUDService:
    return UserCRUDService(session=session)


#dependency function provides admin previlages. 
async def require_admin(current_user: CurrentUserInfo = Depends(auth_manager.get_current_user_from_token)):
    if not current_user or current_user.user_role != get_settings().SECRET_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user