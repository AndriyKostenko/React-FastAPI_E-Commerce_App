from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from shared.customized_json_response import JSONResponse  # type: ignore
from shared.shared_instances import order_service_redis_manager # type: ignore
from schemas. import CreateOrder, UpdateOrder, OrderSchema
from dependencies.dependencies import order_service_dependency

order_routes = APIRouter(tags=["orders"])

@order_routes.post("/orders",response_model=OrderSchema,summary="Create order",response_description="New order created")
@order_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_order(request: Request, order_service: order_service_dependency, order_data: CreateOrder,) -> JSONResponse:
    created_order = await order_service.create_order(order_data=order_data)
    await order_service_redis_manager.clear_cache_namespace(namespace="orders", request=request)
    return JSONResponse(content=created_order, status_code=status.HTTP_201_CREATED)

# @order_routes.get(
#     "/orders",
#     response_model=list[OrderSchema],
#     response_description="All orders",
# )
# # @order_service_redis_manager.cached(ttl=300)
# # @order_service_redis_manager.ratelimiter(times=100, seconds=60)
# async def get_all_orders(
#     request: Request,
#     order_service: order_service_dependency,
#     filters_query: Annotated[OrdersFilterParams, Query()],
# ) -> JSONResponse:
#     orders = await order_service.get_all_orders(filters=filters_query)
#     return JSONResponse(content=orders, status_code=status.HTTP_200_OK)

# @order_routes.get(
#     "/orders/{order_id}",
#     response_model=OrderSchema,
#     response_description="Order by ID",
# )
# # @order_service_redis_manager.cached(ttl=180)
# # @order_service_redis_manager.ratelimiter(times=200, seconds=60)
# async def get_order_by_id(
#     request: Request,
#     order_id: UUID,
#     order_service: order_service_dependency,
# ) -> JSONResponse:
#     order = await order_service.get_order_by_id(order_id=order_id)
#     return JSONResponse(content=order, status_code=status.HTTP_200_OK)

# @order_routes.get(
#     "/orders/user/{user_id}",
#     response_model=list[OrderSchema],
#     response_description="Orders by user ID",
# )
# # @order_service_redis_manager.cached(ttl=180)
# # @order_service_redis_manager.ratelimiter(times=200, seconds=60)
# async def get_orders_by_user_id(
#     request: Request,
#     user_id: UUID,
#     order_service: order_service_dependency,
# ) -> JSONResponse:
#     orders = await order_service.get_orders_by_user_id(user_id=user_id)
#     return JSONResponse(content=orders, status_code=status.HTTP_200_OK)

# @order_routes.patch(
#     "/orders/{order_id}",
#     response_model=OrderSchema,
#     summary="Update order",
#     response_description="Order updated",
# )
# # @order_service_redis_manager.ratelimiter(times=30, seconds=60)
# async def update_order(
#     request: Request,
#     order_id: UUID,
#     order_service: order_service_dependency,
#     order_data: UpdateOrder,
# ) -> JSONResponse:
#     order = await order_service.update_order(order_id=order_id, order_data=order_data)
#     # await order_service_redis_manager.clear_cache_namespace(namespace="orders", request=request)
#     return JSONResponse(content=order, status_code=status.HTTP_200_OK)

# @order_routes.delete(
#     "/orders/{order_id}",
#     response_description="Order deleted",
#     status_code=status.HTTP_204_NO_CONTENT,
# )
# # @order_service_redis_manager.ratelimiter(times=10, seconds=60)
# async def delete_order_by_id(
#     request: Request,
#     order_id: UUID,
#     order_service: order_service_dependency,
# ):
#     await order_service.delete_order_by_id(order_id=order_id)
#     # await order_service_redis_manager.clear_cache_namespace(namespace="orders", request=request)
#     return
