"""payment-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to payment-service.
"""

from uvicorn import run

from app_config import DESCRIPTOR, resolve_resources, payment_service_lifespan
from resources import PaymentApiResources
from config import logger, settings
from routes.payment_routes import payment_routes
from shared.app import DatabaseEngineProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[PaymentApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(payment_service_lifespan, resolve_resources)
    .with_readiness(DatabaseEngineProbe())
    .with_router(payment_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
