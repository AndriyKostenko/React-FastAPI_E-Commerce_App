from uuid import UUID

from fastapi import APIRouter, Request, status

from shared.utils.customized_json_response import JSONResponse
from shared.shared_instances import payment_service_redis_manager
from dependencies.dependencies import payment_service_dependency


payment_routes = APIRouter(tags=["payments"])


@payment_routes.post(
    "/payments/create-intent",
    summary="Create a Stripe PaymentIntent",
    response_description="Stripe client_secret and payment_intent_id returned to the frontend",
)
@payment_service_redis_manager.ratelimiter(times=20, seconds=60)
async def create_payment_intent(
    request: Request,
    payment_service: payment_service_dependency,
) -> JSONResponse:
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
    body = await request.json()
    result = await payment_service.create_payment_intent(
        order_id=UUID(body["order_id"]),
        user_id=UUID(body["user_id"]),
        user_email=body["user_email"],
        amount=int(body["amount"]),
        currency=body.get("currency", "usd"),
    )
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@payment_routes.post(
    "/payments/webhook",
    summary="Stripe webhook receiver",
    response_description="Stripe event processed",
)
async def stripe_webhook(
    request: Request,
    payment_service: payment_service_dependency,
) -> JSONResponse:
    """
    Receives and verifies signed events from Stripe.

    Handled event types:
    - payment_intent.succeeded  → Payment marked succeeded, payment.succeeded published
    - payment_intent.payment_failed → Payment marked failed, payment.failed published

    The Stripe-Signature header is verified against STRIPE_WEBHOOK_SECRET.
    Duplicate events (same Stripe event id) are silently ignored via Redis idempotency.
    """
    payload: bytes = await request.body()
    stripe_signature: str = request.headers.get("stripe-signature", "")

    stripe_event = payment_service.construct_webhook_event(
        payload=payload, stripe_signature=stripe_signature
    )

    event_type: str = stripe_event["type"]
    event_data: dict = stripe_event["data"]

    match event_type:
        case "payment_intent.succeeded":
            await payment_service.handle_payment_intent_succeeded(stripe_event_data=event_data)
        case "payment_intent.payment_failed":
            await payment_service.handle_payment_intent_failed(stripe_event_data=event_data)
        case _:
            # Acknowledge unknown events so Stripe does not keep retrying
            pass

    return JSONResponse(
        content={"received": True, "event_type": event_type},
        status_code=status.HTTP_200_OK,
    )


@payment_routes.get(
    "/payments/{payment_id}",
    summary="Get payment by ID",
)
@payment_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_payment_by_id(
    request: Request,
    payment_id: UUID,
    payment_service: payment_service_dependency,
) -> JSONResponse:
    payment = await payment_service.get_payment_by_id(payment_id)
    return JSONResponse(content=payment, status_code=status.HTTP_200_OK)
