"""shipping-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to shipping-service.
"""

from uvicorn import run

from app_config import DESCRIPTOR, resolve_resources, shipping_service_lifespan
from resources import ShippingApiResources
from service_config import logger, settings
from routes.shipping_routes import shipping_routes
from shared.app import DatabaseEngineProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[ShippingApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(shipping_service_lifespan, resolve_resources)
    .with_readiness(DatabaseEngineProbe())
    .with_router(shipping_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
