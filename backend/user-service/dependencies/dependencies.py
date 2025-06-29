from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserCRUDService
from db.database import database_session_manager
from authentication import auth_manager
from schemas.user_schemas import CurrentUserInfo
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
    
    1.Client sends HTTP request.
    2.FastAPI receives and resolves dependencies for the endpoint.
    3.get_db_session is called as a dependency, which:
     -Calls DatabaseSessionManager.session() (an async context manager).
     -This opens a new AsyncSession for this request.
    4.get_db_session yields this session to the dependency tree.
    5.UserCRUDService receives the session via dependency injection.
    6.Service methods use the session to talk to the DB.
    7.Data flows back up to the FastAPI endpoint, which serializes the result and returns it to the Client.
    8.After the response (or on error), the AsyncSession context manager exits and closes/cleans up.
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


user_crud_dependency = Annotated[UserCRUDService, Depends(get_user_service)]


