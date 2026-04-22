from typing import Any
from logging import Logger

from shared.shared_instances import logger, payment_service_database_session_manager
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.shared_instances import payment_event_idempotency_service
from shared.enums.event_enums import PaymentEvents


class PaymentEventConsumer:
    """
    Consumer for payment-related SAGA responses.

    Currently a skeleton — extend to handle events such as refund requests
    or payment retries triggered by other services.
    """

    def __init__(self, logger: Logger) -> None:
        self.logger: Logger = logger
        self.idempotency_service: IdempotencyEventService = payment_event_idempotency_service

    async def handle_payment_event(self, message: dict[str, Any]) -> None:
        event_type = message.get("event_type")
        match event_type:
            case _:
                self.logger.warning(f"Unhandled payment event type: {event_type}")


payment_event_consumer = PaymentEventConsumer(logger=logger)
