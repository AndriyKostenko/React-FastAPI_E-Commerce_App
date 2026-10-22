from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from schemas.order_schemas import (
    CreateOrder,
    UpdateOrder,
    OrderDetailSchema,
    OrderSchema,
    CancelOrder,
    QuoteOrderRequest,
    QuoteOrderResponse,
    PriceItemsRequest,
    PriceItemsResponse,
    PricedItem,
)
from service_layer.order_pricing_service import OrderPricingService
from dependencies.dependencies import order_service_dependency
from infrastructure.auth.route_guards import AdminDep, CallerDep, SelfOrAdminDep, ensure_owner_or_admin

order_routes = APIRouter(tags=["orders"])


@order_routes.post(
    "/orders/quote",
    response_model=QuoteOrderResponse,
    summary="Build a canonical order quote",
)
async def quote_order(
    caller: CallerDep,
    request: Request,
    order_service: order_service_dependency,
    quote_data: QuoteOrderRequest,
) -> QuoteOrderResponse:
    if order_service.pricing_service is None:
        raise RuntimeError("Order pricing service is unavailable")
    synthetic = CreateOrder(
        user_id=UUID(int=0),
        user_email="quote@example.com",
        products=quote_data.products,
        address=quote_data.address,
        shipping_logistic_name=quote_data.shipping_logistic_name,
    )
    quote = await order_service.pricing_service.build_quote(synthetic)
    return QuoteOrderResponse(
        subtotal_amount=quote.subtotal_amount,
        shipping_amount=quote.shipping_amount,
        tax_amount=quote.tax_amount,
        amount=quote.total_amount,
        amount_cents=quote.amount_cents,
        currency=quote.currency.lower(),
        products=[line.model_dump(mode="json") for line in quote.items],
        shipping_options=quote.shipping_options,
        shipping_logistic_name=quote.shipping_logistic_name,
    )


@order_routes.post(
    "/orders/price-items",
    response_model=PriceItemsResponse,
    summary="Price cart lines as an order would, without shipping or tax",
)
async def price_items(
    order_service: order_service_dependency,
    body: PriceItemsRequest,
) -> PriceItemsResponse:
    # No caller guard: guests have carts too, and this reads prices and writes
    # nothing. The gateway exposes it as the rate-limited public /cart/prices.
    if order_service.pricing_service is None:
        raise RuntimeError("Order pricing service is unavailable")
    outcomes = await order_service.pricing_service.price_cart_lines(body.products)
    return PriceItemsResponse(
        currency="cad",
        items=[
            PricedItem(
                product_id=outcome.line.product_id,
                variant_id=outcome.line.variant_id,
                quantity=outcome.line.quantity,
                unit_price=outcome.line.unit_price,
            )
            if outcome.line is not None
            else PricedItem(
                product_id=outcome.item.id,
                variant_id=outcome.item.variant_id,
                quantity=outcome.item.quantity,
                unit_price=None,
                available=False,
                unavailable_reason=outcome.unavailable_reason,
            )
            for outcome in outcomes
        ],
        subtotal_amount=OrderPricingService.subtotal_of(
            [outcome.line for outcome in outcomes if outcome.line is not None]
        ),
    )


@order_routes.post(
    "/orders",
    response_model=OrderSchema,
    summary="Create order",
    response_description="New order created",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    caller: CallerDep,
    request: Request,
    order_service: order_service_dependency,
    order_data: CreateOrder,
) -> OrderSchema:
    # An order is placed for yourself; only an admin may place one for someone else.
    ensure_owner_or_admin(caller, order_data.user_id)
    return await order_service.create_order(order_data=order_data)


@order_routes.get(
    "/orders",
    response_model=list[OrderSchema],
    status_code=status.HTTP_200_OK,
)
async def get_orders(
    admin: AdminDep,
    request: Request,
    order_service: order_service_dependency,
    # One page, newest first, as the returns queue: the list was the first 50
    # orders ever placed, with no way to reach the rest.
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrderSchema]:
    return await order_service.get_orders(limit=limit, offset=offset)


@order_routes.get(
    "/orders/{order_id}",
    response_model=OrderSchema,
    summary="Get order by ID",
    status_code=status.HTTP_200_OK,
)
async def get_order_by_id(
    caller: CallerDep,
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
) -> OrderSchema:
    order = await order_service.get_order_by_id(order_id=order_id)
    ensure_owner_or_admin(caller, order.user_id)
    return order


@order_routes.get(
    "/orders/{order_id}/details",
    response_model=OrderDetailSchema,
    summary="An order with its address and each line's progress and tracking",
    status_code=status.HTTP_200_OK,
)
async def get_order_detail(
    caller: CallerDep,
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
) -> OrderDetailSchema:
    detail = await order_service.get_order_detail(order_id=order_id)
    # The same rule as GET /orders/{id}: the owner or an admin, nobody else.
    ensure_owner_or_admin(caller, detail.user_id)
    return detail


@order_routes.get(
    "/orders/user/{user_id}",
    response_model=list[OrderSchema],
    summary="Get orders by user ID",
    status_code=status.HTTP_200_OK,
)
async def get_orders_by_user_id(
    caller: SelfOrAdminDep,
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
    admin: AdminDep,
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
    caller: CallerDep,
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
    cancel_data: CancelOrder,
) -> OrderSchema:
    # Ownership is checked before anything changes, not after.
    order = await order_service.get_order_by_id(order_id=order_id)
    ensure_owner_or_admin(caller, order.user_id)
    return await order_service.cancel_order(order_id=order_id, reason=cancel_data.reason)


@order_routes.delete(
    "/orders/{order_id}",
    summary="Delete order",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_order_by_id(
    admin: AdminDep,
    request: Request,
    order_id: UUID,
    order_service: order_service_dependency,
) -> None:
    await order_service.delete_order_by_id(order_id=order_id)
    return None
