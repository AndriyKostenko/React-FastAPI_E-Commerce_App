from typing import Annotated

from fastapi import APIRouter, Query

from dependencies.dependencies import best_seller_service_dependency
from schemas.best_seller_schemas import BestSellerSchema


best_seller_routes = APIRouter(tags=["best sellers"])


@best_seller_routes.get(
    "/best-sellers",
    response_model=list[BestSellerSchema],
    summary="Products ranked by units sold in paid orders, net of refunds",
)
async def get_best_sellers(
    best_seller_service: best_seller_service_dependency,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> list[BestSellerSchema]:
    # No caller guard: it returns product ids and unit counts only, nothing
    # about who bought. The gateway serves it as a public, cached GET.
    return await best_seller_service.rank(days=days, limit=limit)
