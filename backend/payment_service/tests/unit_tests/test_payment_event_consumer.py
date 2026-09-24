"""Unit tests for the capture and release commands PaymentEventConsumer handles."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from events_consumer.payment_event_consumer import PaymentEventConsumer
from shared.contracts.events import PaymentCaptureRequested, PaymentReleaseRequested
from shared.enums.status_enums import PaymentStatus


@pytest.fixture
def payment_service() -> MagicMock:
    service = MagicMock()
    service.capture_payment = AsyncMock(return_value=MagicMock(status=PaymentStatus.SUCCEEDED))
    service.handle_payment_refund = AsyncMock(return_value=MagicMock(status=PaymentStatus.CANCELLED))
    return service


@pytest.fixture
def idempotency() -> MagicMock:
    service = MagicMock()
    service.try_claim_event = AsyncMock(return_value=True)
    service.mark_event_as_processed = AsyncMock()
    service.release_claim = AsyncMock()
    return service


@pytest.fixture
def consumer(payment_service: MagicMock, idempotency: MagicMock) -> PaymentEventConsumer:
    consumer = PaymentEventConsumer(
        logger=MagicMock(),
        settings=MagicMock(),
        database=MagicMock(),
        idempotency_service=idempotency,
        stripe_client=MagicMock(),
    )

    async def _service():
        yield payment_service

    consumer._get_payment_service = _service
    return consumer


def _identity() -> dict:
    return {"order_id": uuid4(), "user_id": uuid4(), "user_email": "buyer@example.com"}


async def test_capture_command_captures_the_orders_payment(consumer, payment_service, idempotency):
    command = PaymentCaptureRequested(**_identity())

    await consumer.handle_payment_event(command.model_dump(mode="json"))

    payment_service.capture_payment.assert_awaited_once_with(order_id=command.order_id)
    assert idempotency.mark_event_as_processed.await_args.kwargs["result"] == "capture_succeeded"


async def test_release_command_voids_or_refunds_the_orders_payment(consumer, payment_service):
    command = PaymentReleaseRequested(**_identity(), reason="Order not found")

    await consumer.handle_payment_event(command.model_dump(mode="json"))

    payment_service.handle_payment_refund.assert_awaited_once_with(order_id=command.order_id)


async def test_failed_capture_releases_claim_for_retry(consumer, payment_service, idempotency):
    payment_service.capture_payment.side_effect = RuntimeError("stripe down")
    command = PaymentCaptureRequested(**_identity())

    with pytest.raises(RuntimeError):
        await consumer.handle_payment_event(command.model_dump(mode="json"))

    idempotency.release_claim.assert_awaited_once()
    idempotency.mark_event_as_processed.assert_not_awaited()
