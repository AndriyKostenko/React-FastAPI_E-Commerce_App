"""cart-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to cart-service.
"""

from uvicorn import run

from app_config import DESCRIPTOR, resolve_resources, cart_service_lifespan
from resources import CartApiResources
from service_config import logger, settings
from routes.cart_routes import cart_routes
from shared.app import DatabaseEngineProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[CartApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(cart_service_lifespan, resolve_resources)
    .with_readiness(DatabaseEngineProbe())
    .with_router(cart_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
