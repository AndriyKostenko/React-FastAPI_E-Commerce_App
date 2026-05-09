from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Request

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import get_current_user, require_admin
from shared.utils.customized_json_response import JSONResponse
from shared.enums.services_enums import Services
from fastapi import Depends
from shared.schemas.user_schemas import CurrentUserInfo


payment_proxy = APIRouter(tags=["Payment Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

@payment_proxy.post("/payments/create-intent", summary="Create a Stripe PaymentIntent")
async def create_payment_intent(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    payload = await request.json()
    override_body = {
        "order_id": payload.get("order_id") or str(uuid4()),
        "user_id": str(current_user.id),
        "user_email": current_user.email,
        "amount": payload.get("amount"),
        "currency": payload.get("currency"),
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
    payment_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
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
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.PAYMENT_SERVICE,
    )
