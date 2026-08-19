"""User-service API resource ownership.

Only cheap, process-local objects are created at import time.  Connections and
other closeable resources are created for each FastAPI lifespan and exposed as
one typed container through ``app.state.resources``.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from logging import Logger
from typing import Any

from fastapi import Request
from httpx import AsyncClient, Limits, Timeout

from shared.managers.cache_manager import CacheManager
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.managers.password_manager import PasswordManager
from shared.managers.ratelimit_manager import RateLimitManager
from shared.managers.token_manager import TokenManager
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("user-service")


@dataclass(slots=True)
class UserApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    cache: CacheManager
    rate_limiter: RateLimitManager
    google_http_client: AsyncClient
    password_manager: PasswordManager
    token_manager: TokenManager


def create_user_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> UserApiResources:
    """Construct resources owned by one user-service ASGI process."""
    return UserApiResources(
        settings=app_settings,
        logger=app_logger,
        database=DatabaseSessionManager(
            database_url=app_settings.USER_SERVICE_DATABASE_URL,
            logger=app_logger,
            echo=app_settings.DEBUG_MODE,
            pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
            reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
            num_db_services=app_settings.PG_DB_SERVICES_COUNT,
        ),
        cache=CacheManager(
            service_prefix="user-service",
            redis_url=app_settings.USER_SERVICE_REDIS_URL,
            logger=app_logger,
            service_api_version=app_settings.USER_SERVICE_URL_API_VERSION,
        ),
        rate_limiter=RateLimitManager(
            service_prefix="user-service",
            redis_url=app_settings.USER_SERVICE_REDIS_URL,
            logger=app_logger,
        ),
        google_http_client=AsyncClient(
            timeout=Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            limits=Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30,
            ),
        ),
        password_manager=PasswordManager(settings=app_settings),
        token_manager=TokenManager(settings=app_settings),
    )


@asynccontextmanager
async def user_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[UserApiResources]:
    """Start and reliably stop all resources owned by the API executable."""
    resources = create_user_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.cache)
        await stack.enter_async_context(resources.rate_limiter)
        await stack.enter_async_context(resources.google_http_client)
        yield resources


def get_user_api_resources(request: Request) -> UserApiResources:
    """Resolve the current app's resource container."""
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, UserApiResources):
        raise RuntimeError("User-service resources are not initialized")
    return resources


def rate_limited(
    times: int,
    seconds: int,
    identifier_param: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Apply the lifespan-owned rate limiter without import-time singletons."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = next(
                (
                    value
                    for value in (*args, *kwargs.values())
                    if isinstance(value, Request)
                ),
                None,
            )
            if request is None:
                raise RuntimeError(f"No Request object supplied to {func.__name__}")

            identifier: str | None = None
            if identifier_param and identifier_param in kwargs:
                value = kwargs[identifier_param]
                identifier_value = (
                    getattr(value, "email", None)
                    or getattr(value, "username", None)
                    or value
                )
                identifier = str(identifier_value)

            await get_user_api_resources(request).rate_limiter.is_rate_limited(
                request=request,
                times=times,
                seconds=seconds,
                identifier=identifier,
            )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
