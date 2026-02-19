from fastapi import APIRouter, Request, status

from shared.customized_json_response import JSONResponse
from shared.shared_instances import order_service_redis_manager
from shared.schemas.order_schemas import CreateOrder, UpdateOrder, OrderSchema
from dependencies.dependencies import order_service_dependency
from events_publisher.order_event_publisher import order_event_publisher


order_routes = APIRouter(tags=["orders"])


@order_routes.post("/orders",response_model=OrderSchema,summary="Create order",response_description="New order created")
@order_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_order(request: Request, order_service: order_service_dependency, order_data: CreateOrder,) -> JSONResponse:
    new_db_order, new_db_order_items = await order_service.create_order(order_data=order_data)
    # publishing order created event
    await order_event_publisher.publish_order_created(order_id=new_db_order.id,
                                                      user_id=new_db_order.user_id,
                                                      items=new_db_order_items,
                                                      total_amount=new_db_order.amount)
    # request inventory reservation (start SAGA)
    await order_event_publisher.publish_inventory_reserve_requested(order_id=new_db_order.id,
                                                                    items=new_db_order_items,
                                                                    user_id=new_db_order.user_id)
    await order_service_redis_manager.clear_cache_namespace(namespace="orders", request=request)
    return JSONResponse(content=new_db_order, status_code=status.HTTP_201_CREATED)

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
