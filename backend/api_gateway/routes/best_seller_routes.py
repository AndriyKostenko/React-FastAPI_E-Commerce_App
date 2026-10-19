"""The home page's Best Sellers: order-service's ranking joined to the products.

order-service knows what sold, product-service what the product is; the
storefront gets both in one call, ranked, so it never assembles them itself.
"""

import asyncio
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, Request
from httpx import Response as HttpxResponse

from resources import RequestScopedGateway, api_gateway_manager, rate_limited
from contracts.services_enums import Services
from infrastructure.utils.customized_json_response import JSONResponse


best_seller_proxy = APIRouter(tags=["Best Sellers"])

# A JSON object as a service returned it; the gateway passes it through unread.
type JsonObject = dict[str, object]


class BestSellerAssembler:
    """Builds the ranked list: [{"units_sold": int, "product": <product detail>}]."""

    def __init__(self, gateway: RequestScopedGateway) -> None:
        self._gateway = gateway

    async def assemble(self, request: Request, *, days: int, limit: int) -> JSONResponse:
        query = urlencode({"days": days, "limit": limit})
        ranking = await self._gateway.request_service(request, Services.ORDER_SERVICE, f"/best-sellers?{query}")
        if not ranking.is_success:
            return self._upstream_error(ranking)
        entries: list[JsonObject] = ranking.json()

        products = await asyncio.gather(*(
            self._gateway.request_service(
                request, Services.PRODUCT_SERVICE, f"/products/{UUID(str(entry['product_id']))}/detailed"
            )
            for entry in entries
        ))

        ranked: list[JsonObject] = []
        for entry, product in zip(entries, products, strict=True):
            # A product deleted since it sold is left out. Any other failure
            # fails the whole answer: a 2xx is cached for everybody, and a list
            # silently missing a product would be served for minutes.
            if product.status_code == 404:
                continue
            if not product.is_success:
                return self._upstream_error(product)
            ranked.append({"units_sold": entry["units_sold"], "product": product.json()})
        return JSONResponse(content=ranked, status_code=200)

    @staticmethod
    def _upstream_error(response: HttpxResponse) -> JSONResponse:
        try:
            content: object = response.json()
        except ValueError:
            content = {"detail": response.text or "Upstream service error"}
        return JSONResponse(content=content, status_code=response.status_code)


best_seller_assembler = BestSellerAssembler(api_gateway_manager)


@best_seller_proxy.get("/best-sellers", summary="Products ranked by units sold in paid orders, net of refunds")
@rate_limited(times=60, seconds=60)
async def get_best_sellers(
    request: Request,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> JSONResponse:
    """PUBLIC - the same answer for every caller, so the gateway caches it for everybody."""
    return await best_seller_assembler.assemble(request, days=days, limit=limit)
