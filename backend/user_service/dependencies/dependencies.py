from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from service_layer.user_service import UserService
from database_layer.user_repository import UserRepository
from shared.shared_instances import user_service_database_session_manager, auth_manager
from shared.schemas.user_schemas import CurrentUserInfo
from shared.shared_instances import settings



"""
FLow Diagram for Database Session Management in FastAPI:

    A[HTTP Request] --> B[FastAPI Router]
    B --> C[get_db_session Dependency]
    C --> D[DatabaseSessionManager.transaction()]
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



async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()

    """
    async with user_service_database_session_manager.transaction() as session:
        yield session


def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserService:
    """Dependency to provide UserService with UserRepository for database operations."""
    return UserService(UserRepository(session=session))



async def require_admin(current_user: CurrentUserInfo = Depends(auth_manager.get_current_user_from_token)):
    if not current_user or current_user.role != settings.SECRET_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


user_crud_dependency = Annotated[UserService, Depends(get_user_service)]
