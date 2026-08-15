from typing import Any
from logging import Logger

from shared.outbox import OutboxRelay
from shared.enums.event_enums import UserEvents
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings
from events_publisher.user_events_publisher import UserEventPublisher
from models.outbox_models import OutboxEvent


async def route_user_event(
    publisher: UserEventPublisher,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Map user-service event types to their publisher methods."""
    routes = {
        UserEvents.USER_REGISTERED: publisher.publish_user_registered,
        UserEvents.USER_EMAIL_VERIFIED: publisher.publish_email_verified,
        UserEvents.USER_PASSWORD_RESET_REQUEST: publisher.publish_password_reset_request,
        UserEvents.USER_PASSWORD_RESET_SUCCESS: publisher.publish_password_reset_success,
        UserEvents.USER_LOGGED_IN: publisher.publish_user_logged_in,
        UserEvents.USER_DELETED: publisher.publish_user_deleted,
    }
    publish = routes.get(event_type)
    if not publish:
        raise ValueError(f"Unsupported user outbox event type: {event_type}")
    await publish(payload)


def build_outbox_relay(
    session_manager: DatabaseSessionManager,
    publisher: UserEventPublisher,
    settings: Settings,
    logger: Logger,
) -> OutboxRelay:
    async def event_router(event_type: str, payload: dict[str, Any]) -> None:
        await route_user_event(publisher, event_type, payload)

    return OutboxRelay(
        session_manager=session_manager,
        event_router=event_router,
        logger=logger,
        poll_interval=float(settings.POLLING_INTERVAL_FROM_DB),
        outbox_model=OutboxEvent,
    )
