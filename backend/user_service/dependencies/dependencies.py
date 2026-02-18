from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer

from service_layer.user_service import UserService
from database_layer.user_repository import UserRepository
from shared.token_manager import TokenManager
from shared.password_manager import PasswordManager
from shared.shared_instances import user_service_database_session_manager, settings
from shared.schemas.user_schemas import CurrentUserInfo

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

# OAuth2PasswordBearer is a class that provides a way to extract the token from the request
# scheme_name is similar to variable name
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=settings.TOKEN_URL,
    scheme_name="oauth2_scheme"
 )

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

def get_password_manager() -> PasswordManager:
    """Provide password manager instance"""
    return PasswordManager(settings)

def get_token_manager() -> TokenManager:
    """Provide token manager instance"""
    return TokenManager(settings)

def get_user_service(session: AsyncSession = Depends(get_db_session),
                    password_manager: PasswordManager = Depends(get_password_manager),
                    token_manager: TokenManager = Depends(get_token_manager)) -> UserService:
    """Dependency to provide UserService with UserRepository for database operations."""
    return UserService(
        repository=UserRepository(session=session),
        password_manager=password_manager,
        token_manager=token_manager
    )

# Type annotations for dependency injection
user_service_dependency = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)],user_service: user_service_dependency) -> CurrentUserInfo:
    """
    Dependency
    - extracts token from request
    - delegetas validation to UserService
    """
    return await user_service.get_current_user_from_token(token)
