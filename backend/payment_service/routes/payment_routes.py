from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, status

from shared.schemas.payment_schemas import (
    PaymentSchema,
    PaymentIntentResponse,
    PaymentResponse,
    WebhookAckResponse,
)
from dependencies.dependencies import payment_service_dependency
from shared.shared_instances import payment_event_idempotency_service as idempotency_service


payment_routes = APIRouter(tags=["payments"])


@payment_routes.post(
    "/payments/create-intent",
    summary="Create a Stripe PaymentIntent",
    response_description="Stripe client_secret and payment_intent_id returned to the frontend",
    response_model=PaymentIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_intent(
    request: Request,
    payment_service: payment_service_dependency,
    payment_data: PaymentSchema,
) -> PaymentIntentResponse:
    result = await payment_service.create_payment_intent(
        order_id=payment_data.order_id,
        user_id=payment_data.user_id,
        user_email=payment_data.user_email,
        amount=payment_data.amount,
        currency=payment_data.currency,
    )
    return PaymentIntentResponse.model_validate(result)


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
            case "payment_intent.succeeded":
                await payment_service.handle_payment_intent_succeeded(stripe_event_data=event_data)
            case "payment_intent.payment_failed":
                await payment_service.handle_payment_intent_failed(stripe_event_data=event_data)
            case "payment_intent.canceled":
                await payment_service.handle_payment_intent_cancelled(stripe_event_data=event_data)
            case "charge.refund.updated":
                await payment_service.handle_charge_refund_updated(stripe_event_data=event_data)
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
    request: Request,
    payment_id: UUID,
    payment_service: payment_service_dependency,
) -> PaymentResponse:
    return await payment_service.get_payment_by_id(payment_id)
