from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Depends, Response

from resources import api_gateway_manager, rate_limited
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from shared.utils.customized_json_response import JSONResponse
from shared.contracts.auth import TokenClaims as CurrentUserInfo


order_proxy = APIRouter(tags=["Order Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

@order_proxy.post("/orders", summary="Create a new order")
@rate_limited(times=10, seconds=60)
async def create_order(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    payload = await request.json()
    # Checkout goes through POST /checkout. An order placed here may never
    # choose its own id, price, or payment reference.
    override_body = {
        **{
            key: value
            for key, value in payload.items()
            if key not in {"id", "amount", "payment_intent_id"}
        },
        "user_id": str(current_user.id),
        "user_email": current_user.email,
    }
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
        override_body=override_body,
    )


@order_proxy.get("/orders", summary="Get all orders")
async def get_all_orders(
    request: Request,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/orders/user/{user_id}", summary="Get orders by user ID")
async def get_orders_by_user_id(request: Request,
                                user_id: UUID,
                                current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/orders/{order_id}", summary="Get order by ID")
async def get_order_by_id(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    upstream = await api_gateway_manager.request_service(
        request, "order-service", f"/orders/{order_id}"
    )
    content = upstream.json()
    if upstream.is_success:
        require_user_or_admin(current_user, target_user_id=UUID(content["user_id"]))
    return JSONResponse(content=content, status_code=upstream.status_code)


# ==================== AUTHENTICATED ENDPOINTS ====================

@order_proxy.patch("/orders/{order_id}/cancel", summary="Cancel an order")
async def cancel_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    upstream = await api_gateway_manager.request_service(
        request, "order-service", f"/orders/{order_id}"
    )
    if upstream.is_success:
        require_user_or_admin(
            current_user, target_user_id=UUID(upstream.json()["user_id"])
        )
    else:
        return JSONResponse(content=upstream.json(), status_code=upstream.status_code)
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.patch("/orders/{order_id}", summary="Update an order")
async def update_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== ADMIN ENDPOINTS ====================

@order_proxy.delete("/orders/{order_id}", summary="Delete an order (admin only)")
async def delete_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== IN-HOUSE PRODUCTION QUEUE (ADMIN) ====================
#
# The queue an operator works to print, pack, and post a custom T-shirt. Every
# path here is admin-only: it exposes a paying customer's shipping address,
# their generated print file, and the controls that move real goods.


@order_proxy.get("/admin/production/jobs", summary="List the in-house production queue")
async def list_production_jobs(
    request: Request,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/admin/production/jobs/{job_id}", summary="Get one production job")
async def get_production_job(
    request: Request,
    job_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get(
    "/admin/production/jobs/{job_id}/artwork",
    summary="Resolve the print-ready artwork download for a job",
)
async def get_production_job_artwork(
    request: Request,
    job_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get(
    "/admin/production/jobs/{job_id}/packing-slip",
    summary="Build the packing slip that ships with the garment",
)
async def get_production_job_packing_slip(
    request: Request,
    job_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.post(
    "/admin/production/jobs/{job_id}/{action}",
    summary="Advance a production job (start, printed, ship, delivered, hold, resume, cancel)",
)
async def advance_production_job(
    request: Request,
    job_id: UUID,
    action: str,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    """Forward one queue transition to order-service.

    The action is passed through rather than enumerated here: order-service
    owns the state machine, so the gateway would only duplicate — and drift
    from — the list of legal moves.
    """
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== REFUNDS (admin) ====================

@order_proxy.post("/admin/orders/{order_id}/refunds", summary="Refund part of an order (admin only)")
async def request_order_refund(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    """Chosen lines (and quantities), optionally shipping; order-service validates
    against what is still refundable and payment-service makes the refund."""
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/admin/orders/{order_id}/refunds", summary="List an order's refunds (admin only)")
async def list_order_refunds(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== RETURNS ====================
#
# The customer's routes only need a signed-in caller: order-service loads the
# order and allows its owner (or an admin), so ownership is decided once, by
# the service that knows who owns what.


@order_proxy.get("/orders/{order_id}/returns/eligibility", summary="Which lines can be returned, and until when")
async def get_return_eligibility(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)


@order_proxy.post("/orders/{order_id}/returns", summary="Ask to return delivered units (multipart, with photos)")
@rate_limited(times=10, seconds=60)
async def request_return(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)


@order_proxy.get("/orders/{order_id}/returns", summary="The returns asked for on an order")
async def list_order_returns(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)


@order_proxy.post("/orders/{order_id}/returns/{return_id}/cancel", summary="Withdraw an undecided return")
async def cancel_return(
    request: Request,
    order_id: UUID,
    return_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)


@order_proxy.get("/admin/returns", summary="The returns queue (admin only)")
async def list_returns(
    request: Request,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)


@order_proxy.get("/admin/returns/{return_id}", summary="One return (admin only)")
async def get_return(
    request: Request,
    return_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)


@order_proxy.get("/admin/returns/{return_id}/photos/{index}", summary="One evidence photo (admin only)")
async def get_return_photo(
    request: Request,
    return_id: UUID,
    index: int,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    """The image bytes as they are: forward_request would re-wrap a non-JSON body as JSON."""
    upstream = await api_gateway_manager.request_service(
        request, "order-service", f"/admin/returns/{return_id}/photos/{index}"
    )
    if not upstream.is_success:
        return JSONResponse(content=upstream.json(), status_code=upstream.status_code)
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type"),
        headers={"Cache-Control": "private, no-store"},
    )


@order_proxy.post(
    "/admin/returns/{return_id}/{action}",
    summary="Decide a return: approve, receive or reject (admin only)",
)
async def decide_return(
    request: Request,
    return_id: UUID,
    action: Literal["approve", "receive", "reject"],
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(service_name="order-service", request=request)
