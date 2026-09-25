from uuid import UUID

from fastapi import APIRouter, Depends, status

from dependencies.dependencies import order_refund_service_dependency
from schemas.order_refund_schemas import OrderRefundSchema, RefundRequest
from shared.auth.route_guards import AdminDep, require_admin


# Refunds move money: admin-only end to end, guarded at the router.
refund_routes = APIRouter(
    tags=["refunds"],
    prefix="/admin/orders",
    dependencies=[Depends(require_admin)],
)


@refund_routes.post(
    "/{order_id}/refunds",
    response_model=OrderRefundSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Refund part of an order (chosen lines, optionally shipping)",
)
async def request_refund(
    order_id: UUID,
    admin: AdminDep,
    refund: RefundRequest,
    refund_service: order_refund_service_dependency,
) -> OrderRefundSchema:
    return await refund_service.request(order_id, refund, requested_by=admin.user_id)


@refund_routes.get(
    "/{order_id}/refunds",
    response_model=list[OrderRefundSchema],
    summary="Refunds recorded for an order",
)
async def list_refunds(order_id: UUID, refund_service: order_refund_service_dependency) -> list[OrderRefundSchema]:
    return await refund_service.list_for_order(order_id)
