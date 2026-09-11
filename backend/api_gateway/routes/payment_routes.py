from fastapi import APIRouter, Request, Depends

from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from resources import api_gateway_manager
from shared.utils.customized_json_response import JSONResponse
from shared.enums.services_enums import Services
from shared.contracts.auth import TokenClaims as CurrentUserInfo


payment_proxy = APIRouter(tags=["Payment Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

# PaymentIntents are opened only by POST /checkout, which reads the amount from
# the order it just placed. There is deliberately no client-facing route here.


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
