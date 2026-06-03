from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, status

from shared.schemas.order_schemas import CreateOrder, UpdateOrder, OrderSchema, CancelOrder
from dependencies.dependencies import order_service_dependency
from models.order_models import Order

order_routes = APIRouter(tags=["orders"])


@order_routes.post(
    "/orders",
    response_model=OrderSchema,
    summary="Create order",
    response_description="New order created",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    request: Request,
    order_service: order_service_dependency,
    order_data: CreateOrder,
) -> OrderSchema:
    return await order_service.create_order(order_data=order_data)


@order_routes.get(
    "/orders",
    response_model=list[OrderSchema],
    status_code=status.HTTP_200_OK,
)
async def get_orders(
    request: Request,
    order_service: order_service_dependency,
) -> list[OrderSchema]:
    return await order_service.get_orders()


@order_routes.get(
    "/orders/{order_id}",
    response_model=OrderSchema,
    summary="Get order by ID",
    status_code=status.HTTP_200_OK,
)
async def get_order_by_id(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
) -> OrderSchema:
    return await order_service.get_order_by_id(order_id=order_id)


@order_routes.get(
    "/orders/user/{user_id}",
    response_model=list[OrderSchema],
    summary="Get orders by user ID",
    status_code=status.HTTP_200_OK,
)
async def get_orders_by_user_id(
    request: Request,
    user_id: UUID,
    order_service: order_service_dependency,
) -> list[OrderSchema]:
    return await order_service.get_orders_by_user_id(user_id=user_id)


@order_routes.patch(
    "/orders/{order_id}",
    response_model=OrderSchema,
    summary="Update order",
    status_code=status.HTTP_200_OK,
)
async def update_order(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
    order_data: UpdateOrder,
) -> OrderSchema:
    return await order_service.update_order(order_id=order_id, order_data=order_data)


@order_routes.patch(
    "/orders/{order_id}/cancel",
    response_model=OrderSchema,
    summary="Cancel an order",
    status_code=status.HTTP_200_OK,
)
async def cancel_order(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
    cancel_data: CancelOrder,
) -> OrderSchema:
    return await order_service.cancel_order(order_id=order_id, reason=cancel_data.reason)


@order_routes.delete(
    "/orders/{order_id}",
    summary="Delete order",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_order_by_id(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
) -> None:
    await order_service.delete_order_by_id(order_id=order_id)
    return None


@order_routes.get(
    "/admin/schema/orders",
    summary="Schema for AdminJS",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_order_schema_for_admin_js(request: Request) -> dict[str, Any]:
    return {"fields": Order.get_admin_schema()}
