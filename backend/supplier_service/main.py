"""supplier-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to supplier-service.
"""

from uvicorn import run

from app_config import (
    DESCRIPTOR,
    build_exception_handlers,
    resolve_resources,
    supplier_service_lifespan,
)
from resources import SupplierApiResources, logger, settings
from routes.supplier_routes import supplier_routes
from shared.app import DatabaseEngineProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[SupplierApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(supplier_service_lifespan, resolve_resources)
    .with_readiness(DatabaseEngineProbe())
    .with_exception_handlers(build_exception_handlers())
    .with_router(supplier_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run(
        "main:app",
        host=DESCRIPTOR.host,
        port=DESCRIPTOR.port,
        reload=settings.DEBUG_MODE,
    )
