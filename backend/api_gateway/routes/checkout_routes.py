"""Checkout orchestration: price a cart, place the order, then open its payment.

The order is created *before* the Stripe PaymentIntent, and the intent's
amount is read from that order. The client never states an amount and never
names an order it does not own, so what the card is authorized for is always
exactly what order_service priced.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from httpx import Response as HttpxResponse

from dependencies.auth_dependencies import get_current_user
from resources import api_gateway_manager, rate_limited
from shared.contracts.auth import TokenClaims as CurrentUserInfo
from shared.enums.services_enums import Services
from shared.utils.customized_json_response import JSONResponse


checkout_proxy = APIRouter(tags=["Checkout"])

# Fields a checkout request may contribute to an order. Identity, price and
# payment references are always set server-side.
_ORDER_INPUT_FIELDS = ("products", "address", "shipping_logistic_name")


def _upstream_error(response: HttpxResponse) -> JSONResponse:
    try:
        content: Any = response.json()
    except ValueError:
        content = {"detail": response.text or "Upstream service error"}
    return JSONResponse(content=content, status_code=response.status_code)


def _order_input(payload: dict[str, Any]) -> dict[str, Any]:
    return {field: payload.get(field) for field in _ORDER_INPUT_FIELDS}


@checkout_proxy.post("/checkout/quote", summary="Price a cart, with shipping options, for an address")
@rate_limited(times=30, seconds=60)
async def quote_checkout(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    response = await api_gateway_manager.request_service(
        request,
        Services.ORDER_SERVICE,
        "/orders/quote",
        method="POST",
        json=_order_input(payload),
    )
    if not response.is_success:
        return _upstream_error(response)
    return JSONResponse(content=response.json(), status_code=200)


@checkout_proxy.post("/checkout", summary="Place the order and open its payment")
@rate_limited(times=10, seconds=60)
async def start_checkout(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    """Create a pending order and a PaymentIntent for exactly its total.

    Sending ``order_id`` resumes payment for an order the caller already
    placed, e.g. after a card decline or a page reload. The PaymentIntent is
    idempotent per order, so resuming returns the same intent.
    """
    payload: dict[str, Any] = await request.json()
    raw_order_id = payload.get("order_id")

    if raw_order_id:
        try:
            order_id = UUID(str(raw_order_id))
        except ValueError:
            return JSONResponse(content={"detail": "order_id must be a UUID"}, status_code=422)
        order_response = await api_gateway_manager.request_service(
            request, Services.ORDER_SERVICE, f"/orders/{order_id}"
        )
        if not order_response.is_success:
            return _upstream_error(order_response)
        order = order_response.json()
        # Not found rather than forbidden: never confirm another user's order exists.
        if order.get("user_id") != str(current_user.id):
            return JSONResponse(content={"detail": "Order not found"}, status_code=404)
        if order.get("status") != "pending":
            # ``order_status`` lets the client tell an order that was already
            # placed (never place it again) from one that was cancelled.
            return JSONResponse(
                content={
                    "detail": "Order is no longer awaiting payment",
                    "order_status": order.get("status"),
                },
                status_code=409,
            )
        created_now = False
    else:
        order_response = await api_gateway_manager.request_service(
            request,
            Services.ORDER_SERVICE,
            "/orders",
            method="POST",
            json={
                **_order_input(payload),
                "user_id": str(current_user.id),
                "user_email": current_user.email,
            },
        )
        if not order_response.is_success:
            return _upstream_error(order_response)
        order = order_response.json()
        created_now = True

    intent_response = await api_gateway_manager.request_service(
        request,
        Services.PAYMENT_SERVICE,
        "/payments/create-intent",
        method="POST",
        json={
            "order_id": order["id"],
            "user_id": str(current_user.id),
            "user_email": current_user.email,
            "amount": order["amount_cents"],
            "currency": order["currency"],
            # Read from the order, never from the client, like the amount.
            "tax_calculation_id": order.get("tax_calculation_id"),
        },
    )
    if not intent_response.is_success:
        if created_now:
            # An order nobody can pay for would only hold inventory until the
            # Saga timeout; release it now.
            await api_gateway_manager.request_service(
                request,
                Services.ORDER_SERVICE,
                f"/orders/{order['id']}/cancel",
                method="PATCH",
                json={"reason": "Payment could not be initialised"},
            )
        elif intent_response.status_code == 409:
            # The card for this order is already authorized: it was placed.
            return JSONResponse(
                content={
                    "detail": "This order has already been paid for",
                    "order_status": "payment_authorized",
                },
                status_code=409,
            )
        return _upstream_error(intent_response)

    intent = intent_response.json()
    return JSONResponse(
        content={
            "order_id": order["id"],
            "client_secret": intent["client_secret"],
            "payment_intent_id": intent["stripe_payment_intent_id"],
            "currency": order["currency"],
            "amount_cents": order["amount_cents"],
            "total_amount": order["amount"],
            "subtotal_amount": order.get("subtotal_amount"),
            "shipping_amount": order.get("shipping_amount"),
            "tax_amount": order.get("tax_amount"),
            "shipping_logistic_name": order.get("shipping_logistic_name"),
        },
        status_code=201 if created_now else 200,
    )
