"""API-gateway process resources and request-time accessors."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from logging import Logger
from typing import Any

from fastapi import Request

from gateway.apigateway import ApiGateway
from middleware.auth_middleware import AuthMiddleware
from middleware.cache_middleware import GatewayRequestMiddleware
from shared.managers.cache_manager import CacheManager
from shared.managers.logger_manager import setup_logger
from shared.managers.ratelimit_manager import RateLimitManager
from shared.managers.token_manager import TokenManager
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
    )
    gateway = ApiGateway(settings=app_settings, logger=app_logger)
    auth = AuthMiddleware(
        settings=app_settings,
        logger=app_logger,
        token_manager=TokenManager(settings=app_settings),
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
    )


@asynccontextmanager
async def api_gateway_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[ApiGatewayResources]:
    resources = create_api_gateway_resources(app_settings, app_logger)
    try:
        await resources.cache.connect()
        await resources.rate_limiter.connect()
        await resources.gateway.startup()
        yield resources
    finally:
        try:
            await resources.gateway.shutdown()
        finally:
            try:
                await resources.rate_limiter.close()
            finally:
                await resources.cache.close()


def get_api_gateway_resources(request: Request) -> ApiGatewayResources:
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, ApiGatewayResources):
        raise RuntimeError("API-gateway resources are not initialized")
    return resources


def get_api_gateway(request: Request) -> ApiGateway:
    return get_api_gateway_resources(request).gateway


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
