from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from config import settings
from dependencies.dependencies import order_return_service_dependency
from schemas.order_return_schemas import (
    ReturnDecision,
    ReturnEligibility,
    ReturnRejection,
    ReturnRequestCreate,
    ReturnRequestSchema,
)
from shared.auth.route_guards import AdminDep, CallerDep, require_admin
from shared.contracts.returns import ReturnStatus


# ------------------------------------------------------------------ customer
#
# The owner of the order (or an admin) — checked by the service once the
# order is loaded, since only then is the owner known.

return_routes = APIRouter(tags=["returns"])


@return_routes.get(
    "/orders/{order_id}/returns/eligibility",
    response_model=ReturnEligibility,
    summary="Which lines of an order can be returned, how many units, until when",
)
async def return_eligibility(
    order_id: UUID, caller: CallerDep, return_service: order_return_service_dependency
) -> ReturnEligibility:
    return await return_service.eligibility(order_id, caller)


@return_routes.post(
    "/orders/{order_id}/returns",
    response_model=ReturnRequestSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Ask to return delivered units (multipart: a JSON `request` field plus `photos`)",
)
async def request_return(
    order_id: UUID,
    caller: CallerDep,
    return_service: order_return_service_dependency,
    request: Annotated[str, Form(description="ReturnRequestCreate as JSON")],
    photos: Annotated[list[UploadFile], File(description="JPEG, PNG or WebP evidence")] = [],
) -> ReturnRequestSchema:
    try:
        create = ReturnRequestCreate.model_validate_json(request)
    except ValidationError as exc:
        # The same 422 shape a JSON body would have produced.
        raise RequestValidationError(exc.errors(include_url=False, include_context=False)) from exc
    if len(photos) > settings.RETURN_PHOTO_MAX_COUNT:
        # Refused before reading any of them.
        uploads = [b""] * len(photos)
    else:
        # One byte over the limit is enough for the service to refuse it.
        uploads = [await photo.read(settings.RETURN_PHOTO_MAX_BYTES + 1) for photo in photos]
    return await return_service.request(order_id, caller, create, uploads)


@return_routes.get(
    "/orders/{order_id}/returns",
    response_model=list[ReturnRequestSchema],
    summary="The returns asked for on an order",
)
async def list_order_returns(
    order_id: UUID, caller: CallerDep, return_service: order_return_service_dependency
) -> list[ReturnRequestSchema]:
    return await return_service.list_for_order(order_id, caller)


@return_routes.post(
    "/orders/{order_id}/returns/{return_id}/cancel",
    response_model=ReturnRequestSchema,
    summary="Withdraw a return that has not been decided yet",
)
async def cancel_return(
    order_id: UUID, return_id: UUID, caller: CallerDep, return_service: order_return_service_dependency
) -> ReturnRequestSchema:
    return await return_service.cancel(order_id, return_id, caller)


# --------------------------------------------------------------------- admin
#
# Deciding a return moves money: admin-only end to end, guarded at the router.

admin_return_routes = APIRouter(
    tags=["returns"],
    prefix="/admin/returns",
    dependencies=[Depends(require_admin)],
)


@admin_return_routes.get("", response_model=list[ReturnRequestSchema], summary="The returns queue, oldest first")
async def list_returns(
    return_service: order_return_service_dependency,
    status_filter: Annotated[ReturnStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReturnRequestSchema]:
    return await return_service.list_queue(status_filter, limit=limit, offset=offset)


@admin_return_routes.get("/{return_id}", response_model=ReturnRequestSchema, summary="One return")
async def get_return(return_id: UUID, return_service: order_return_service_dependency) -> ReturnRequestSchema:
    return await return_service.get(return_id)


@admin_return_routes.get(
    "/{return_id}/photos/{index}",
    response_class=Response,
    summary="One evidence photo of a return",
)
async def get_return_photo(
    return_id: UUID, index: int, return_service: order_return_service_dependency
) -> Response:
    content, content_type = await return_service.photo(return_id, index)
    # Private evidence: never kept by a shared cache.
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "private, no-store"})


@admin_return_routes.post(
    "/{return_id}/approve",
    response_model=ReturnRequestSchema,
    summary="Approve: returnless lines are refunded now, the rest when received",
)
async def approve_return(
    return_id: UUID, admin: AdminDep, decision: ReturnDecision, return_service: order_return_service_dependency
) -> ReturnRequestSchema:
    return await return_service.approve(return_id, admin.user_id, decision.note)


@admin_return_routes.post(
    "/{return_id}/receive",
    response_model=ReturnRequestSchema,
    summary="The goods came back and passed inspection: refund them",
)
async def receive_return(
    return_id: UUID, admin: AdminDep, decision: ReturnDecision, return_service: order_return_service_dependency
) -> ReturnRequestSchema:
    return await return_service.receive(return_id, admin.user_id, decision.note)


@admin_return_routes.post(
    "/{return_id}/reject",
    response_model=ReturnRequestSchema,
    summary="Refuse a request, or close an approved return whose goods never came back",
)
async def reject_return(
    return_id: UUID, admin: AdminDep, rejection: ReturnRejection, return_service: order_return_service_dependency
) -> ReturnRequestSchema:
    return await return_service.reject(return_id, admin.user_id, rejection.note)
