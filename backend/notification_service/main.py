"""notification-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to notification-service.
"""

from uvicorn import run

from app_config import DESCRIPTOR, resolve_resources, notification_service_lifespan
from resources import NotificationApiResources
from resources import logger, settings
from routes.notification_routes import notification_routes
from shared.app import DatabaseEngineProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[NotificationApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(notification_service_lifespan, resolve_resources)
    .with_tracing(instrument_sqlalchemy=False)
    .with_readiness(DatabaseEngineProbe())
    .with_router(notification_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
