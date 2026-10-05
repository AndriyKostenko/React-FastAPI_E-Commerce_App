"""
Stripe webhook signatures, checked with Stripe's own verifier: a correctly
signed payload is accepted, anything else is a 400 (never a 500, which Stripe
would keep retrying as if the service were broken).
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe
from starlette.requests import Request

from exceptions.payment_exceptions import InvalidStripeWebhookSignature
from service_layer.payment_service import PaymentService

SECRET = "whsec_test_signing_secret"
PAYLOAD = b'{"id": "evt_1", "object": "event", "type": "payment_intent.created", "data": {"object": {"id": "pi_1"}}}'


def _service() -> PaymentService:
    settings = SimpleNamespace(
        STRIPE_API_KEY="sk_test_unused",
        STRIPE_WEBHOOK_SIGNING_SECRET=SECRET,
        FULL_STRIPE_WEBHOOK_ENDPOINT="https://example.test/webhook",
        STRIPE_MAX_NETWORK_RETRIES=0,
    )
    return PaymentService(
        repository=MagicMock(), outbox_event_service=MagicMock(), settings=settings, logger=MagicMock()
    )


def _signature(payload: bytes, secret: str = SECRET) -> str:
    timestamp = int(time.time())
    signed = stripe.WebhookSignature._compute_signature(f"{timestamp}.{payload.decode()}", secret)
    return f"t={timestamp},v1={signed}"


def _request(payload: bytes, signature: str) -> Request:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/payments/webhook",
            "headers": [(b"stripe-signature", signature.encode()), (b"content-type", b"application/json")],
        },
        receive,
    )


async def test_a_correctly_signed_event_is_accepted() -> None:
    event = await _service().construct_webhook_event(_request(PAYLOAD, _signature(PAYLOAD)))
    assert event.id == "evt_1"


@pytest.mark.parametrize(
    ("payload", "signature"),
    [
        (PAYLOAD, _signature(PAYLOAD, secret="whsec_someone_else")),
        # The same event, re-serialised on the way: the bytes Stripe signed are gone.
        (PAYLOAD.replace(b": ", b":"), _signature(PAYLOAD)),
    ],
    ids=["wrong-secret", "altered-bytes"],
)
async def test_a_signature_that_does_not_verify_is_a_400(payload: bytes, signature: str) -> None:
    with pytest.raises(InvalidStripeWebhookSignature) as raised:
        await _service().construct_webhook_event(_request(payload, signature))
    assert raised.value.status_code == 400
