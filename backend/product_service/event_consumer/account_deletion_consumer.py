from logging import Logger
from typing import Any

from contracts.event_enums import UserEvents
from contracts.events import UserDeletedEvent
from infrastructure.idempotency.idempotency_service import IdempotencyEventService
from service_layer.deleted_account_cleanup import DeletedAccountCleanup


class AccountDeletionConsumer:
    """Consumes user.deleted: what product-service holds about the account goes (DeletedAccountCleanup)."""

    def __init__(
        self, cleanup: DeletedAccountCleanup, idempotency_service: IdempotencyEventService, logger: Logger
    ) -> None:
        self._cleanup = cleanup
        self._idempotency = idempotency_service
        self._logger = logger

    async def handle_user_event(self, message: dict[str, Any]) -> None:
        match message.get("event_type"):
            case UserEvents.USER_DELETED:
                await self.handle_user_deleted(message)
            case other:
                self._logger.warning(f"Unhandled user event type: {other}")

    async def handle_user_deleted(self, message: dict[str, Any]) -> None:
        event = UserDeletedEvent(**message)
        if not await self._idempotency.try_claim_event(event.event_id, event.event_type):
            self._logger.info(f"Skipping duplicate user.deleted event for user {event.user_id}")
            return
        try:
            if event.user_id is None:
                self._logger.warning("user.deleted without a user id; nothing to delete")
            else:
                await self._cleanup.forget(event.user_id)
            await self._idempotency.mark_event_as_processed(event.event_id, event.event_type, None, "forgotten")
        except Exception:
            # Released, so the consumer's retry queue delivers it again.
            await self._idempotency.release_claim(event.event_id, event.event_type)
            raise
