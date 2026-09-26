from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from schemas.payment_schemas import (
    PaymentSchema,
    PaymentIntentResponse,
    PaymentResponse,
    WebhookAckResponse,
)
from dependencies.dependencies import (
    payment_dispute_service_dependency,
    idempotency_service_dependency,
    payment_service_dependency,
    tax_calculation_service_dependency,
)
from shared.auth.route_guards import AdminDep, CallerDep, ensure_owner_or_admin
from shared.auth.service_assertion import require_service
from shared.contracts.tax import TaxCalculationRequest, TaxCalculationResult

# Called by order-service directly while it prices an order; only a request
# order-service signed with its own key is accepted.
OrderServiceCaller = Annotated[str, Depends(require_service("order-service"))]


payment_routes = APIRouter(tags=["payments"])


@payment_routes.post(
    "/payments/create-intent",
    summary="Create a Stripe PaymentIntent",
    response_description="Stripe client_secret and payment_intent_id returned to the frontend",
    response_model=PaymentIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_intent(
    caller: CallerDep,
    request: Request,
    payment_service: payment_service_dependency,
    payment_data: PaymentSchema,
) -> PaymentIntentResponse:
    ensure_owner_or_admin(caller, payment_data.user_id)
    result = await payment_service.create_payment_intent(
        order_id=payment_data.order_id,
        user_id=payment_data.user_id,
        user_email=payment_data.user_email,
        amount=payment_data.amount,
        currency=payment_data.currency,
        tax_calculation_id=payment_data.tax_calculation_id,
    )
    return PaymentIntentResponse.model_validate(result)


@payment_routes.post(
    "/payments/tax/calculate",
    summary="Calculate the sales tax on a priced order (order-service only)",
    response_model=TaxCalculationResult,
    status_code=status.HTTP_200_OK,
)
async def calculate_tax(
    caller_service: OrderServiceCaller,
    tax_request: TaxCalculationRequest,
    tax_service: tax_calculation_service_dependency,
) -> TaxCalculationResult:
    return await tax_service.calculate(tax_request)


@payment_routes.post(
    "/payments/webhook",
    summary="Stripe webhook receiver",
    response_description="Stripe event processed",
    response_model=WebhookAckResponse,
    status_code=status.HTTP_200_OK,
)
async def stripe_webhook(
    request: Request,
    payment_service: payment_service_dependency,
    idempotency_service: idempotency_service_dependency,
    dispute_service: payment_dispute_service_dependency,
) -> WebhookAckResponse:
    stripe_event = await payment_service.construct_webhook_event(request=request)
    event_type: str = stripe_event["type"]
    event_data: dict[str, Any] = stripe_event["data"]
    event_id: str = stripe_event["id"]
    claimed = await idempotency_service.try_claim_event(event_id=event_id, event_type=event_type)
    if not claimed:
        return WebhookAckResponse(
            received=True,
            event_type=event_type,
            idempotency="duplicate",
        )
    try:
        match event_type:
            case "payment_intent.amount_capturable_updated":
                await payment_service.handle_payment_intent_amount_capturable_updated(
                    stripe_event_data=event_data
                )
            case "payment_intent.succeeded":
                await payment_service.handle_payment_intent_succeeded(stripe_event_data=event_data)
            case "payment_intent.payment_failed":
                await payment_service.handle_payment_intent_failed(stripe_event_data=event_data)
            case "payment_intent.canceled":
                await payment_service.handle_payment_intent_cancelled(stripe_event_data=event_data)
            case "charge.refund.updated":
                await payment_service.handle_charge_refund_updated(stripe_event_data=event_data)
            case "charge.dispute.created":
                await dispute_service.opened(event_data)
            case "charge.dispute.updated":
                await dispute_service.updated(event_data)
            case "charge.dispute.closed":
                await dispute_service.closed(event_data)
            case _:
                pass

        await idempotency_service.mark_event_as_processed(
            event_id=event_id,
            event_type=event_type,
            order_id=event_data.get("object", {}).get("metadata", {}).get("order_id"),
            result="processed",
        )
    except Exception:
        await idempotency_service.release_claim(event_id=event_id, event_type=event_type)
        raise

    return WebhookAckResponse(received=True, event_type=event_type)


@payment_routes.get(
    "/payments",
    summary="List all payments (admin)",
    response_model=list[PaymentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_payments(
    admin: AdminDep,
    request: Request,
    payment_service: payment_service_dependency,
) -> list[PaymentResponse]:
    return await payment_service.get_payments()


@payment_routes.get(
    "/payments/{payment_id}",
    summary="Get payment by ID",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_payment_by_id(
    caller: CallerDep,
    request: Request,
    payment_id: UUID,
    payment_service: payment_service_dependency,
) -> PaymentResponse:
    # Previously any signed-in user could read any payment by id.
    payment = await payment_service.get_payment_by_id(payment_id)
    ensure_owner_or_admin(caller, payment.user_id)
    return payment
