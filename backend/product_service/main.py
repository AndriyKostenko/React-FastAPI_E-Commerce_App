"""product-service ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to product-service.
"""

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from uvicorn import run

from app_config import DESCRIPTOR, product_service_lifespan, resolve_resources
from resources import ProductApiResources, logger, settings
from routes.artwork_routes import artwork_routes
from routes.category_routes import category_routes
from routes.product_image_routes import product_images_routes
from routes.product_routes import product_routes
from routes.review_routes import review_routes
from shared.app import DatabaseEngineProbe, RedisPingProbe, ServiceAppBuilder

app = (
    ServiceAppBuilder[ProductApiResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(product_service_lifespan, resolve_resources)
    # This service caches catalogue reads in Redis, so a dead cache is a
    # not-ready signal rather than a slow request.
    .with_readiness(DatabaseEngineProbe(), RedisPingProbe("cache"))
    .with_router(product_routes, prefix=DESCRIPTOR.api_prefix)
    .with_router(category_routes, prefix=DESCRIPTOR.api_prefix)
    .with_router(review_routes, prefix=DESCRIPTOR.api_prefix)
    .with_router(product_images_routes, prefix=DESCRIPTOR.api_prefix)
    .with_router(artwork_routes, prefix=DESCRIPTOR.api_prefix)
    .build()
)

# Generated artwork and product images are served straight off disk; the gateway
# proxies /media through to here so the frontend keeps one origin.
_media_dir = Path(os.getenv("MEDIA_ROOT", "./media"))
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
