from logging import Logger
from typing import Any

from shared.shared_instances import (
    logger,
    wishlist_event_idempotency_service,
    wishlist_service_database_session_manager,
)
from shared.enums.event_enums import UserEvents
from shared.schemas.event_schemas import UserDeletedEvent
from database_layer.wishlist_repository import WishlistRepository
from service_layer.wishlist_service import WishlistService


class WishlistEventConsumer:
    """
    Consumes domain events that affect wishlists.

    Currently handles:
    - user.deleted: deletes the user's wishlist and all its items.
    """

    def __init__(self, logger: Logger) -> None:
        self.logger: Logger = logger
        self.idempotency_service = wishlist_event_idempotency_service

    async def _get_wishlist_service(self):
        """Create a WishlistService with a fresh database session."""
        async with wishlist_service_database_session_manager.transaction() as session:
            yield WishlistService(repository=WishlistRepository(session=session))

    async def handle_user_event(self, message: dict[str, Any]) -> None:
        """Route user events to the appropriate handler."""
        event_type = message.get("event_type")

        match event_type:
            case UserEvents.USER_DELETED:
                await self.handle_user_deleted(message)
            case _:
                self.logger.warning(f"Unhandled wishlist consumer event type: {event_type}")

    async def handle_user_deleted(self, message: dict[str, Any]) -> None:
        """Delete the user's wishlist when the user is deleted."""
        event = UserDeletedEvent(**message)

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(
                    f"Skipping duplicate user.deleted event for wishlist — user: {event.user_id}"
                )
                return

            self.logger.info(
                f"Deleting wishlist for user {event.user_id} after user deletion"
            )

            async for wishlist_service in self._get_wishlist_service():
                await wishlist_service.delete_wishlist_by_user_id(user_id=event.user_id)

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                user_id=event.user_id,
                result="wishlist_deleted",
            )
            self.logger.info(
                f"Wishlist deleted for user {event.user_id} after user deletion"
            )

        except Exception as e:
            await self.idempotency_service.release_claim(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            self.logger.error(
                f"Error deleting wishlist for user {message.get('user_id')}: {e}"
            )
            raise


wishlist_event_consumer = WishlistEventConsumer(logger=logger)
