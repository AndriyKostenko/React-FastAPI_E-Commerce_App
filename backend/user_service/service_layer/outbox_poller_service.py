from typing import Any

from shared.outbox import OutboxRelay
from shared.enums.event_enums import UserEvents
from events_publisher.user_events_publisher import UserEventPublisher
from models.outbox_models import OutboxEvent
from managers import UserOutboxResources


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


def build_outbox_relay(resources: UserOutboxResources) -> OutboxRelay:
    async def event_router(event_type: str, payload: dict[str, Any]) -> None:
        await route_user_event(resources.publisher, event_type, payload)

    return OutboxRelay(
        session_manager=resources.database,
        event_router=event_router,
        logger=resources.logger,
        poll_interval=float(resources.settings.POLLING_INTERVAL_FROM_DB),
        outbox_model=OutboxEvent,
    )
