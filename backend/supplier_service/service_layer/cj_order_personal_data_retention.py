"""
Removes the customer's details from CJ orders that ended long enough ago.

``request_payload`` keeps the order exactly as it was sent to CJ, which is
what settles a dispute with CJ about it: products, quantities, shipping
method, the province and country it went to. It also holds the customer's
name, street, city, postal code, phone and email, and the attempt keeps the
email for tracking updates. Neither is needed once the order has ended, so
after CJ_ORDER_PERSONAL_DATA_RETENTION_DAYS they are removed and the rest stays.
"""

from datetime import datetime, timedelta, timezone
from logging import Logger

from pydantic import JsonValue

from database_layer.cj_order_attempt_repository import CJOrderAttemptRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager

# The createOrderV2 keys that identify the customer (CJShippingAddress.as_cj_fields, CJOrderPayloadBuilder).
PERSONAL_FIELDS: frozenset[str] = frozenset({
    "shippingCustomerName",
    "shippingPhone",
    "shippingAddress",
    "shippingAddress2",
    "shippingCity",
    "shippingZip",
    "email",
})


class CJOrderPersonalDataRetention:
    """Strips the customer's details from ended CJ orders once they are older than the retention period."""

    def __init__(
        self,
        database: DatabaseSessionManager,
        logger: Logger,
        retention_days: int,
        batch_size: int = 200,
    ) -> None:
        self._database = database
        self._logger = logger
        self._retention_days = retention_days
        self._batch_size = batch_size

    async def prune(self, now: datetime | None = None) -> int:
        """Remove the details from every order that ended before the cutoff; how many orders."""
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self._retention_days)
        removed = 0
        while True:
            async with self._database.transaction() as session:
                attempts = await CJOrderAttemptRepository(session).ended_with_personal_data(cutoff, self._batch_size)
                for attempt in attempts:
                    attempt.request_payload = self.without_personal_fields(attempt.request_payload)
                    attempt.user_email = None
                    attempt.personal_data_removed_at = now
            removed += len(attempts)
            if len(attempts) < self._batch_size:
                break
        self._logger.info("Removed customer details from %s CJ orders that ended before %s", removed, cutoff.date())
        return removed

    @staticmethod
    def without_personal_fields(payload: dict[str, JsonValue] | None) -> dict[str, JsonValue] | None:
        if payload is None:
            return None
        # A new dict, so SQLAlchemy sees the JSON column change.
        return {key: value for key, value in payload.items() if key not in PERSONAL_FIELDS}
