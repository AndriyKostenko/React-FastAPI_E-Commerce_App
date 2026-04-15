from uuid import UUID, uuid4
from typing import Any

from database_layer.notification_repository import NotificationRepository
from exceptions.notification_exceptions import NotificationNotFoundError, NotificationAccessDeniedError
from models.notification_models import Notification
from shared.schemas.notifications_schemas import NotificationInfo, NotificationsFilterParams


class NotificationService:
    """Service layer for notification CRUD and consumer save operations."""

    def __init__(self, repository: NotificationRepository):
        self.repository: NotificationRepository = repository

    # ─── Read ────────────────────────────────────────────────────────────────

    async def get_user_notifications(self,
                                    user_id: UUID,
                                    params: NotificationsFilterParams) -> list[NotificationInfo]:
        filters: dict[str, Any] = {}
        if params.is_read is not None:
            filters["is_read"] = params.is_read
        if params.notification_type is not None:
            filters["notification_type"] = params.notification_type

        date_filters: dict[str, Any] = {}
        if params.date_created_from:
            date_filters["date_created_from"] = params.date_created_from
        if params.date_created_to:
            date_filters["date_created_to"] = params.date_created_to

        notifications = await self.repository.get_by_user_id(
            user_id=user_id,
            filters=filters,
            sort_by=params.sort_by,
            sort_order=params.sort_order,
            limit=params.limit,
            offset=params.offset,
            date_filters=date_filters or None,
        )
        return [NotificationInfo.model_validate(n) for n in notifications]

    async def get_notification_by_id(self,
                                    notification_id: UUID,
                                    requesting_user_id: UUID | None = None) -> NotificationInfo:
        notification = await self.repository.get_by_id(notification_id)
        if not notification:
            raise NotificationNotFoundError()
        if requesting_user_id and notification.user_id and notification.user_id != requesting_user_id:
            raise NotificationAccessDeniedError()
        return NotificationInfo.model_validate(notification)

    async def get_unread_count(self, user_id: UUID) -> int:
        return await self.repository.get_unread_count(user_id)

    # ─── Update ──────────────────────────────────────────────────────────────

    async def mark_as_read(self,
                           notification_id: UUID,
                           requesting_user_id: UUID | None = None) -> NotificationInfo:
        notification = await self.repository.get_by_id(notification_id)
        if not notification:
            raise NotificationNotFoundError()
        if requesting_user_id and notification.user_id and notification.user_id != requesting_user_id:
            raise NotificationAccessDeniedError()
        notification.is_read = True
        updated = await self.repository.update(notification)
        return NotificationInfo.model_validate(updated)

    async def mark_all_as_read(self, user_id: UUID) -> dict[str, int]:
        updated_count = await self.repository.mark_all_as_read(user_id)
        return {"updated": updated_count}

    # ─── Delete ──────────────────────────────────────────────────────────────

    async def delete_notification(self, notification_id: UUID, requesting_user_id: UUID | None = None) -> None:
        notification = await self.repository.get_by_id(notification_id)
        if not notification:
            raise NotificationNotFoundError()
        if requesting_user_id and notification.user_id and notification.user_id != requesting_user_id:
            raise NotificationAccessDeniedError()
        await self.repository.delete(notification)

    # ─── Consumer ────────────────────────────────────────────────────────────

    async def save_notification(self,
                                message: str,
                                notification_type: str,
                                user_id: UUID | None = None) -> NotificationInfo:
        """Persist a notification record. Called from the event consumer."""
        notification = await self.repository.create(Notification(
            id=uuid4(),
            user_id=user_id,
            message=message,
            notification_type=notification_type,
            is_read=False,
        ))
        return NotificationInfo.model_validate(notification)
