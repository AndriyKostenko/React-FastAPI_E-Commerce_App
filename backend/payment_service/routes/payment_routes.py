from uuid import UUID
from typing import Any

from fastapi import APIRouter, Request, status

from shared.utils.customized_json_response import JSONResponse
from shared.schemas.payment_schemas import PaymentSchema
from shared.shared_instances import payment_service_redis_manager
from dependencies.dependencies import payment_service_dependency
from shared.shared_instances import payment_event_idempotency_service as idempotency_service


payment_routes = APIRouter(tags=["payments"])


@payment_routes.post("/payments/create-intent",
                    summary="Create a Stripe PaymentIntent",
                    response_description="Stripe client_secret and payment_intent_id returned to the frontend",)
@payment_service_redis_manager.ratelimiter(times=20, seconds=60)
async def create_payment_intent(request: Request,
                                payment_service: payment_service_dependency,
                                payment_data: PaymentSchema) -> JSONResponse:
    """
    Called by the frontend before order confirmation.

    Expects JSON body:
        {
            "order_id": "<uuid>",
            "user_id": "<uuid>",
            "user_email": "user@example.com",
            "amount": 9999,       # in cents
            "currency": "usd"
        }

    Returns:
        {
            "client_secret": "pi_xxx_secret_yyy",
            "stripe_payment_intent_id": "pi_xxx",
            "payment_id": "<uuid>"
        }
    """
    result = await payment_service.create_payment_intent(
        order_id=payment_data.order_id,
        user_id=payment_data.user_id,
        user_email=payment_data.user_email,
        amount=payment_data.amount,
        currency=payment_data.currency,
    )
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@payment_routes.post("/payments/webhook",summary="Stripe webhook receiver",response_description="Stripe event processed")
async def stripe_webhook(request: Request,
                         payment_service: payment_service_dependency) -> JSONResponse:
    """
    Receives and verifies signed events from Stripe.

    Handled event types:
    - payment_intent.succeeded  → Payment marked succeeded, payment.succeeded published
    - payment_intent.payment_failed → Payment marked failed, payment.failed published

    The Stripe-Signature header is verified against STRIPE_WEBHOOK_SECRET.
    Duplicate events (same Stripe event id) are silently ignored via Redis idempotency.
    """
    stripe_event = await payment_service.construct_webhook_event(request=request)
    event_type: str = stripe_event["type"] 
    event_data: dict[str ,Any] = stripe_event["data"] 
    event_id: str = stripe_event["id"]
    claimed = await idempotency_service.try_claim_event(event_id=event_id, event_type=event_type)
    if not claimed:
        # Event has already been processed by another instance, acknowledge without processing
        return JSONResponse(
            content={"received": True, "event_type": event_type, "idempotency": "duplicate"},
            status_code=status.HTTP_200_OK,
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
                # Acknowledge unknown events so Stripe does not keep retrying
                pass

        await idempotency_service.mark_event_as_processed(
            event_id=event_id,
            event_type=event_type,
            order_id=event_data.get("object", {}).get("metadata", {}).get("order_id"),
            result="processed",
        )
    except Exception as e:
        # On error, release the claim so the event can be retried immediately
        await idempotency_service.release_claim(event_id=event_id, event_type=event_type)
        raise e

    return JSONResponse(
        content={"received": True, "event_type": event_type},
        status_code=status.HTTP_200_OK,
    )


@payment_routes.get("/payments/{payment_id}",summary="Get payment by ID",)
@payment_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_payment_by_id(
    request: Request,
    payment_id: UUID,
    payment_service: payment_service_dependency,
) -> JSONResponse:
    payment = await payment_service.get_payment_by_id(payment_id)
    return JSONResponse(content=payment, status_code=status.HTTP_200_OK)


@payment_routes.get("/payments", summary="List all payments (admin)")
@payment_service_redis_manager.ratelimiter(times=50, seconds=60)
async def get_payments(
    request: Request,
    payment_service: payment_service_dependency,
) -> JSONResponse:
    payments = await payment_service.get_payments()
    return JSONResponse(content=payments, status_code=status.HTTP_200_OK)
