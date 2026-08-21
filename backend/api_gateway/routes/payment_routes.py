from uuid import uuid4

from fastapi import APIRouter, Request, Depends

from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from resources import api_gateway_manager, rate_limited
from shared.utils.customized_json_response import JSONResponse
from shared.enums.services_enums import Services
from shared.contracts.auth import TokenClaims as CurrentUserInfo


payment_proxy = APIRouter(tags=["Payment Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

@payment_proxy.post("/payments/create-intent", summary="Create a Stripe PaymentIntent")
@rate_limited(times=10, seconds=60)
async def create_payment_intent(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    payload: dict = await request.json()
    products = payload.get("products")
    if not isinstance(products, list) or not products:
        return JSONResponse(
            content={"detail": "At least one product is required"},
            status_code=422,
        )
    quote_response = await api_gateway_manager.request_service(
        request,
        "order-service",
        "/orders/quote",
        method="POST",
        json={"products": products},
    )
    if not quote_response.is_success:
        return JSONResponse(
            content=quote_response.json(),
            status_code=quote_response.status_code,
        )
    quote = quote_response.json()
    override_body = {
        "order_id": payload.get("order_id") or str(uuid4()),
        "user_id": str(current_user.id),
        "user_email": current_user.email,
        "amount": round(float(quote["amount"]) * 100),
        "currency": quote["currency"],
    }
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.PAYMENT_SERVICE,
        override_body=override_body,
    )


@payment_proxy.post(
    "/payments/webhook",
    summary="Stripe webhook receiver (called by Stripe — no auth required)",
)
async def stripe_webhook(request: Request) -> JSONResponse:
    """Public endpoint — Stripe sends signed webhook events here directly."""
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.PAYMENT_SERVICE,
    )


# ==================== AUTHENTICATED ENDPOINTS ====================

@payment_proxy.get("/payments/{payment_id}", summary="Get payment by ID")
async def get_payment_by_id(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    require_user_or_admin(current_user=current_user)
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.PAYMENT_SERVICE,
    )


# ==================== ADMIN ENDPOINTS ====================

@payment_proxy.get("/payments", summary="List all payments (admin only)")
async def get_payments(
    request: Request,
    current_user: CurrentUserInfo = Depends(require_admin),
) -> JSONResponse:
    require_admin(current_user=current_user)
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.PAYMENT_SERVICE,
    )
