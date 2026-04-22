from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from models.notification_models import Notification
from shared.database_layer.database_layer import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """Extends BaseRepository with notification-specific query methods."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Notification)

    async def get_by_user_id(self,
                            user_id: UUID,
                            filters: dict[str, Any] | None = None,
                            sort_by: str = "date_created",
                            sort_order: str = "desc",
                            limit: int = 50,
                            offset: int = 0,
                            date_filters: dict[str, Any] | None = None) -> list[Notification]:
        """Get all notifications for a specific user with optional filtering."""
        base_filters = {"user_id": user_id}
        if filters:
            base_filters.update(filters)
        return await self.get_all(
            filters=base_filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            date_filters=date_filters,
        )

    async def get_unread_count(self, user_id: UUID) -> int:
        """Return the number of unread notifications for a user."""
        return await self.count(user_id=user_id, is_read=False)

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all unread notifications for a user as read. Returns count updated."""
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        await self.session.flush()
        return result.rowcount
