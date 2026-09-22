"""api-gateway ASGI entrypoint.

Assembly — middleware order, health probes, the Prometheus endpoint and the
exception contract — lives in ``shared.app``; this module only states what is
specific to the gateway.
"""

from fastapi import HTTPException, Request
from fastapi.responses import Response as PlainResponse
from httpx import RequestError
from uvicorn import run

from app_config import (
    DESCRIPTOR,
    api_gateway_lifespan,
    authentication_middleware,
    build_exception_handlers,
    gateway_middleware,
    resolve_resources,
)
from resources import ApiGatewayResources, get_api_gateway_resources, logger, settings
from routes.cart_routes import cart_proxy
from routes.checkout_routes import checkout_proxy
from routes.notification_routes import notification_proxy
from routes.order_routes import order_proxy
from routes.payment_routes import payment_proxy
from routes.product_routes import product_proxy
from routes.shipping_routes import shipping_proxy
from routes.supplier_routes import supplier_proxy
from routes.user_routes import user_proxy
from routes.wishlist_routes import wishlist_proxy
from shared.app import ServiceAppBuilder

PROXIES = (
    (user_proxy, "User Service Proxy"),
    (product_proxy, "Product Service Proxy"),
    (supplier_proxy, "Supplier Service Proxy"),
    (order_proxy, "Order Service Proxy"),
    (notification_proxy, "Notification Service Proxy"),
    (payment_proxy, "Payment Service Proxy"),
    (checkout_proxy, "Checkout"),
    (cart_proxy, "Cart Service Proxy"),
    (shipping_proxy, "Shipping Service Proxy"),
    (wishlist_proxy, "Wishlist Service Proxy"),
)

builder = (
    ServiceAppBuilder[ApiGatewayResources](DESCRIPTOR, settings=settings, logger=logger)
    .with_lifespan(api_gateway_lifespan, resolve_resources)
    # The gateway owns no database or Redis of its own; liveness is all it can
    # honestly answer, so readiness is declared with no probes and stays 200
    # while the process is up.
    .with_readiness()
    # The edge terminates the browser's Host header; Traefik has already matched
    # the router rule by the time a request reaches here.
    .without_host_validation()
    # gateway_requests_total / gateway_request_duration_seconds are recorded
    # inside gateway_middleware and are what the Grafana gateway panels query.
    .without_request_metrics()
    .without_instrumentator()
    .with_tracing(instrument_sqlalchemy=False)
    # Order matters: gateway_middleware is registered first and so becomes the
    # INNER layer, guaranteeing tokens are validated before a cache lookup or a
    # rate-limit bucket is touched.
    .with_http_middleware(gateway_middleware, authentication_middleware)
    .with_exception_handlers(build_exception_handlers())
)

for proxy, tag in PROXIES:
    builder.with_router(proxy, prefix=DESCRIPTOR.api_prefix, tags=[tag])

app = builder.build()


@app.get("/media/{file_path:path}", include_in_schema=False)
async def proxy_product_media(request: Request, file_path: str):
    """
    Proxy product-service static media through API Gateway so frontend can use a
    single API origin (:8000) for both JSON APIs and generated image files.
    """
    normalized_path = file_path.lstrip("/")
    if not normalized_path:
        raise HTTPException(status_code=404, detail="Media file not found")

    upstream_url = f"{settings.PRODUCT_SERVICE_URL.rstrip('/')}/media/{normalized_path}"
    try:
        gateway = get_api_gateway_resources(request).gateway
        upstream_response = await gateway.client.get(
            upstream_url,
            timeout=gateway._TIMEOUT,
        )
    except RequestError as exc:
        logger.error(f"Failed to fetch media from product-service ({upstream_url}): {exc!r}")
        raise HTTPException(status_code=502, detail="Failed to fetch media file")

    passthrough_headers: dict[str, str] = {}
    for header in ("cache-control", "etag", "last-modified", "accept-ranges", "content-range"):
        value = upstream_response.headers.get(header)
        if value:
            passthrough_headers[header] = value

    return PlainResponse(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
        headers=passthrough_headers,
    )


if __name__ == "__main__":
    run("main:app", host=DESCRIPTOR.host, port=DESCRIPTOR.port, reload=True)
