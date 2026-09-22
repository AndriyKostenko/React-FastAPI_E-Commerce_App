"""user-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to user-service.
"""

from fastapi.middleware.gzip import GZipMiddleware
from uvicorn import run

from app_config import DESCRIPTOR, resolve_resources, user_service_lifespan
from managers import UserApiResources, logger, settings
from routes.user_routes import user_routes
from shared.app import DatabaseEngineProbe, RedisPingProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[UserApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(user_service_lifespan, resolve_resources)
    # Readiness gates on everything a request actually touches: the DB engine and
    # both Redis-backed managers. The session registry shares Redis with the
    # gateway and is not this service's to declare unhealthy.
    .with_readiness(
        DatabaseEngineProbe(),
        RedisPingProbe("cache"),
        RedisPingProbe("rate_limiter"),
    )
    .with_middleware(GZipMiddleware, minimum_size=1024)
    .with_router(user_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
