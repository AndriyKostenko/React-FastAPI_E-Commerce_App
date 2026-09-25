"""API-gateway process resources and request-time accessors."""

from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from logging import Logger
from typing import Any

from fastapi import Request
from starlette.requests import HTTPConnection

from gateway.apigateway import ApiGateway
from middleware.auth_middleware import AuthMiddleware
from middleware.cache_middleware import GatewayRequestMiddleware
from shared.managers.cache_manager import CacheManager
from shared.managers.logger_manager import setup_logger
from shared.managers.ratelimit_manager import RateLimitManager
from shared.auth.user_tokens import UserTokenVerifier
from shared.managers.session_registry import SessionRegistry
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("api-gateway")


@dataclass(slots=True)
class ApiGatewayResources:
    settings: Settings
    logger: Logger
    cache: CacheManager
    rate_limiter: RateLimitManager
    gateway: ApiGateway
    auth: AuthMiddleware
    request_middleware: GatewayRequestMiddleware
    session_registry: SessionRegistry


def create_api_gateway_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> ApiGatewayResources:
    """Construct resources owned by one API-gateway ASGI process."""
    cache = CacheManager(
        service_prefix="api-gateway",
        redis_url=app_settings.APIGATEWAY_SERVICE_REDIS_URL,
        logger=app_logger,
        service_api_version=app_settings.API_GATEWAY_SERVICE_URL_API_VERSION,
    )
    rate_limiter = RateLimitManager(
        service_prefix="api-gateway",
        redis_url=app_settings.APIGATEWAY_SERVICE_REDIS_URL,
        logger=app_logger,
        trusted_proxy_networks=app_settings.TRUSTED_PROXY_NETWORKS,
    )
    gateway = ApiGateway(settings=app_settings, logger=app_logger)
    # Written by user-service when a session is revoked; read here so a token
    # from a superseded generation is refused on every proxied request.
    session_registry = SessionRegistry(
        service_prefix="api-gateway",
        redis_url=app_settings.SESSION_REGISTRY_REDIS_URL,
        logger=app_logger,
    )
    auth = AuthMiddleware(
        settings=app_settings,
        logger=app_logger,
        # Public key only: the gateway can check a session but never mint one.
        token_verifier=UserTokenVerifier.from_settings(app_settings),
        session_registry=session_registry,
    )
    return ApiGatewayResources(
        settings=app_settings,
        logger=app_logger,
        cache=cache,
        rate_limiter=rate_limiter,
        gateway=gateway,
        auth=auth,
        request_middleware=GatewayRequestMiddleware(
            cache_manager=cache,
            rate_limit_manager=rate_limiter,
        ),
        session_registry=session_registry,
    )


@asynccontextmanager
async def api_gateway_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[ApiGatewayResources]:
    resources = create_api_gateway_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.cache)
        await stack.enter_async_context(resources.rate_limiter)
        await stack.enter_async_context(resources.gateway)
        await stack.enter_async_context(resources.session_registry)
        yield resources


def get_api_gateway_resources(connection: HTTPConnection) -> ApiGatewayResources:
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, ApiGatewayResources):
        raise RuntimeError("API-gateway resources are not initialized")
    return resources


def get_api_gateway(connection: HTTPConnection) -> ApiGateway:
    return get_api_gateway_resources(connection).gateway


class RequestScopedGateway:
    """Thin route adapter; the real gateway remains owned by ``app.state``."""

    async def forward_request(
        self,
        request: Request,
        service_name: str,
        override_body: dict[str, Any] | None = None,
    ) -> Any:
        return await get_api_gateway(request).forward_request(
            request=request,
            service_name=service_name,
            override_body=override_body,
        )

    async def request_service(
        self,
        request: Request,
        service_name: str,
        path: str,
        *,
        method: str = "GET",
        json: dict[str, Any] | None = None,
    ) -> Any:
        return await get_api_gateway(request).request_service(
            service_name,
            path,
            method=method,
            json=json,
        )


api_gateway_manager = RequestScopedGateway()


def rate_limited(
    times: int,
    seconds: int,
    identifier_param: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Resolve the app-owned rate limiter when the route is called."""
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

            await get_api_gateway_resources(request).rate_limiter.is_rate_limited(
                request=request,
                times=times,
                seconds=seconds,
                identifier=identifier,
            )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
