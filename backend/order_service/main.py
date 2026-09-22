"""order-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to order-service.
"""

from uvicorn import run

from app_config import DESCRIPTOR, resolve_resources, order_service_lifespan
from resources import OrderApiResources
from config import logger, settings
from routes.orders_routes import order_routes
from routes.production_routes import production_routes
from shared.app import DatabaseEngineProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[OrderApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(order_service_lifespan, resolve_resources)
    .with_readiness(DatabaseEngineProbe())
    .with_router(order_routes, prefix=DESCRIPTOR.api_prefix)
    .with_router(production_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
