from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer
from httpx import AsyncClient

from service_layer.user_service import UserService
from models.outbox_models import OutboxEvent
from database_layer.user_repository import UserRepository
from shared.database_layer.outbox_repository import OutboxRepository
from service_layer.outbox_event_service import OutboxEventService
from shared.managers.token_manager import TokenManager
from shared.managers.password_manager import PasswordManager
from resources import UserApiResources, get_user_api_resources, settings
from schemas.user_schemas import CurrentUserInfo


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

async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()
    """
    async with get_user_api_resources(request).database.transaction() as session:
        yield session

def get_password_manager(request: Request) -> PasswordManager:
    """Provide password manager instance"""
    return get_user_api_resources(request).password_manager

def get_token_manager(request: Request) -> TokenManager:
    """Provide token manager instance"""
    return get_user_api_resources(request).token_manager

def get_outbox_event_service(session: AsyncSession = Depends(get_db_session)) -> OutboxEventService:
    """Dependency to provide OutboxEventService for transactional event publishing."""
    return OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent))

def get_google_http_client(request: Request) -> AsyncClient:
    """Provide the shared Google HTTP client from application state."""
    return get_user_api_resources(request).google_http_client


def get_resources(request: Request) -> UserApiResources:
    """Expose the typed resource container to dependency composition."""
    return get_user_api_resources(request)


def get_user_service(session: AsyncSession = Depends(get_db_session),
                     password_manager: PasswordManager = Depends(get_password_manager),
                     token_manager: TokenManager = Depends(get_token_manager),
                     outbox_event_service: OutboxEventService = Depends(get_outbox_event_service),
                     google_http_client: AsyncClient = Depends(get_google_http_client),
                     resources: UserApiResources = Depends(get_resources)) -> UserService:
    """Dependency to provide UserService with UserRepository for database operations."""
    return UserService(
        repository=UserRepository(session=session),
        password_manager=password_manager,
        token_manager=token_manager,
        cache_manager=resources.cache,
        outbox_event_service=outbox_event_service,
        http_client=google_http_client,
        settings=resources.settings,
    )

# Type annotations for dependency injection
user_service_dependency = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], user_service: user_service_dependency) -> CurrentUserInfo:
    """
    Dependency
    - extracts token from request
    - delegates validation to UserService
    """
    return await user_service.get_current_user_from_token(token)

current_user_dependency = Annotated[CurrentUserInfo, Depends(get_current_user)]


def require_roles(*roles: str):
    """Factory creating a dependency to enforce RBAC role checking."""
    async def _require_roles(current_user: current_user_dependency) -> CurrentUserInfo:
        if current_user.role not in roles:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return current_user
    return _require_roles


admin_only_dependency = Annotated[CurrentUserInfo, Depends(require_roles(settings.SECRET_ROLE))]


async def self_or_admin(user_id: UUID, current_user: current_user_dependency) -> CurrentUserInfo:
    """Dependency ensuring caller is either an admin or the subject of the operation."""
    if current_user.role != settings.SECRET_ROLE and current_user.id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


self_or_admin_dependency = Annotated[CurrentUserInfo, Depends(self_or_admin)]
