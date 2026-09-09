"""User-service API resource ownership.

One process — the ASGI app — is served from here.  Its resource graph is:

* ``UserApiResources``: a pure container, so a test can assemble the graph from
  doubles without touching the network;
* ``ResourceManager``: builds that container (cheap, no I/O), owns its lifetime
  (opening every connection and unwinding them in reverse), and owns both ends
  of the ``app.state`` contract.

The outbox relay process has its own, smaller graph in ``managers.outbox_manager``.
"""

from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from functools import wraps
from logging import Logger
from types import TracebackType
from typing import Any, Final

from fastapi import FastAPI, Request
from httpx import AsyncClient, Limits, Timeout
from starlette.requests import HTTPConnection

from shared.managers.cache_manager import CacheManager
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.managers.password_manager import PasswordManager
from shared.managers.ratelimit_manager import RateLimitManager
from shared.managers.session_registry import SessionRegistry
from shared.managers.token_manager import TokenManager
from shared.settings import Settings, get_settings


SERVICE_NAME: Final[str] = "user-service"

settings: Settings = get_settings()
logger: Logger = setup_logger(SERVICE_NAME)


def build_database(app_settings: Settings, app_logger: Logger) -> DatabaseSessionManager:
    """The database manager is configured identically in every process."""
    return DatabaseSessionManager(
        database_url=app_settings.USER_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )


@dataclass(slots=True)
class UserApiResources:
    """Everything one user-service ASGI process needs, resolved per request."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    cache: CacheManager
    rate_limiter: RateLimitManager
    google_http_client: AsyncClient
    password_manager: PasswordManager
    token_manager: TokenManager
    session_registry: SessionRegistry


class ResourceManager:
    """Builds and owns the resources of one user-service API process.

    ``attach`` writes the container to ``app.state`` and ``resolve`` reads it
    back, so the attribute name is defined in exactly one place instead of being
    restated by every consumer.

    Typical use from a FastAPI lifespan::

        async with ResourceManager() as resources:
            ResourceManager.attach(app, resources)
            ...
    """

    STATE_ATTRIBUTE: Final[str] = "resources"

    def __init__(self, app_settings: Settings = settings, app_logger: Logger = logger) -> None:
        self.settings = app_settings
        self.logger = app_logger
        self._stack: AsyncExitStack | None = None

    # ---------------------------- construction ----------------------------

    def build(self) -> UserApiResources:
        """Assemble the API resource graph without opening any connection."""
        return UserApiResources(
            settings=self.settings,
            logger=self.logger,
            database=build_database(self.settings, self.logger),
            cache=CacheManager(
                service_prefix=SERVICE_NAME,
                redis_url=self.settings.USER_SERVICE_REDIS_URL,
                logger=self.logger,
                service_api_version=self.settings.USER_SERVICE_URL_API_VERSION,
            ),
            rate_limiter=RateLimitManager(
                service_prefix=SERVICE_NAME,
                redis_url=self.settings.USER_SERVICE_REDIS_URL,
                logger=self.logger,
                trusted_proxy_networks=self.settings.TRUSTED_PROXY_NETWORKS,
            ),
            google_http_client=AsyncClient(
                timeout=Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
                limits=Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
            ),
            password_manager=PasswordManager(settings=self.settings),
            token_manager=TokenManager(settings=self.settings),
            # Shared with the API gateway, which reads it to refuse access
            # tokens from a session generation the user has already revoked.
            session_registry=SessionRegistry(
                service_prefix=SERVICE_NAME,
                redis_url=self.settings.SESSION_REGISTRY_REDIS_URL,
                logger=self.logger,
            ),
        )

    # ----------------------------- lifecycle ------------------------------

    async def __aenter__(self) -> UserApiResources:
        if self._stack is not None:
            raise RuntimeError(f"{type(self).__name__} is already open")
        resources = self.build()
        stack = AsyncExitStack()
        await stack.__aenter__()
        self._stack = stack
        try:
            # The HTTP client is constructed already open, so it is registered
            # first: a failure while starting the database, cache, or rate
            # limiter then still closes it.
            await stack.enter_async_context(resources.google_http_client)
            await stack.enter_async_context(resources.database)
            await stack.enter_async_context(resources.cache)
            await stack.enter_async_context(resources.session_registry)
            await stack.enter_async_context(resources.rate_limiter)
        except BaseException:
            # Unwind whatever started before re-raising, then allow a retry.
            self._stack = None
            await stack.aclose()
            raise
        return resources

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.__aexit__(exc_type, exc_value, traceback)

    # --------------------------- app.state contract -----------------------

    @classmethod
    def attach(cls, app: FastAPI, resources: UserApiResources) -> None:
        """Publish the container for request-scoped dependencies."""
        setattr(app.state, cls.STATE_ATTRIBUTE, resources)

    @classmethod
    def detach(cls, app: FastAPI) -> None:
        """Remove the container; safe to call even if it was never attached."""
        if getattr(app.state, cls.STATE_ATTRIBUTE, None) is not None:
            delattr(app.state, cls.STATE_ATTRIBUTE)

    @classmethod
    def resolve(cls, connection: HTTPConnection) -> UserApiResources:
        """Resolve the current app's resource container."""
        resources = getattr(connection.app.state, cls.STATE_ATTRIBUTE, None)
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

            await ResourceManager.resolve(request).rate_limiter.is_rate_limited(
                request=request,
                times=times,
                seconds=seconds,
                identifier=identifier,
            )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
