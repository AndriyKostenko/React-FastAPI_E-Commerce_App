from uuid import UUID

from fastapi import APIRouter, Request, status

from shared.utils.customized_json_response import JSONResponse
from shared.schemas.order_schemas import CreateOrder, UpdateOrder, OrderSchema, CancelOrder
from dependencies.dependencies import order_service_dependency
from models.order_models import Order

order_routes = APIRouter(tags=["orders"])


@order_routes.post("/orders",
                    response_model=OrderSchema,
                    summary="Create order",
                    response_description="New order created")
async def create_order(request: Request, order_service: order_service_dependency, order_data: CreateOrder,) -> JSONResponse:
    new_db_order = await order_service.create_order(order_data=order_data)
    return JSONResponse(content=new_db_order, status_code=status.HTTP_201_CREATED)


@order_routes.get("/orders",
                    response_model=list[OrderSchema])
async def get_orders(request: Request,
                    order_service: order_service_dependency) -> JSONResponse:
    orders = await order_service.get_orders()
    return JSONResponse(content=orders, status_code=status.HTTP_200_OK)


@order_routes.get("/orders/{order_id}",
                  response_model=OrderSchema,
                  summary="Get order by ID")
async def get_order_by_id(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
) -> JSONResponse:
    order = await order_service.get_order_by_id(order_id=order_id)
    return JSONResponse(content=order, status_code=status.HTTP_200_OK)


@order_routes.get("/orders/user/{user_id}",
                  response_model=list[OrderSchema],
                  summary="Get orders by user ID")
async def get_orders_by_user_id(
    request: Request,
    user_id: UUID,
    order_service: order_service_dependency,
) -> JSONResponse:
    orders = await order_service.get_orders_by_user_id(user_id=user_id)
    return JSONResponse(content=orders, status_code=status.HTTP_200_OK)


@order_routes.patch("/orders/{order_id}",
                    response_model=OrderSchema,
                    summary="Update order")
async def update_order(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
    order_data: UpdateOrder,
) -> JSONResponse:
    order = await order_service.update_order(order_id=order_id, order_data=order_data)
    return JSONResponse(content=order, status_code=status.HTTP_200_OK)


@order_routes.patch("/orders/{order_id}/cancel",
                    response_model=OrderSchema,
                    summary="Cancel an order")
async def cancel_order(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
    cancel_data: CancelOrder,
) -> JSONResponse:
    order = await order_service.cancel_order(order_id=order_id, reason=cancel_data.reason)
    return JSONResponse(content=order, status_code=status.HTTP_200_OK)


@order_routes.delete("/orders/{order_id}",
                     summary="Delete order",
                     status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_by_id(
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
):
    await order_service.delete_order_by_id(order_id=order_id)
    return


@order_routes.get("/admin/schema/orders", summary="Schema for AdminJS")
async def get_order_schema_for_admin_js(request: Request):
    return JSONResponse(
        content={"fields": Order.get_admin_schema()}, status_code=status.HTTP_200_OK
    )
