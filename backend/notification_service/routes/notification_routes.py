from uuid import UUID

from fastapi import APIRouter, status, Request, Query

from shared.schemas.notifications_schemas import (
    NotificationInfo,
    NotificationsFilterParams,
    BulkMarkReadResponse,
    UnreadCountResponse,
)
from dependencies.dependencies import notification_service_dependency


notification_routes = APIRouter(tags=["notification-service"])


@notification_routes.get(
    "/notifications/users/{user_id}",
    summary="Get all notifications for a user",
    response_model=list[NotificationInfo],
    status_code=status.HTTP_200_OK,
)
async def get_user_notifications(
    request: Request,
    user_id: UUID,
    notification_service: notification_service_dependency,
    is_read: bool | None = Query(default=None),
    notification_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="date_created"),
    sort_order: str = Query(default="desc"),
) -> list[NotificationInfo]:
    """Retrieve all notifications for a given user with optional filtering."""
    params = NotificationsFilterParams(
        is_read=is_read,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await notification_service.get_user_notifications(
        user_id=user_id,
        params=params,
    )


@notification_routes.get(
    "/notifications/users/{user_id}/unread-count",
    summary="Get unread notification count for a user",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
)
async def get_unread_count(
    request: Request,
    user_id: UUID,
    notification_service: notification_service_dependency,
) -> UnreadCountResponse:
    """Return the number of unread notifications for a user."""
    count = await notification_service.get_unread_count(user_id=user_id)
    return UnreadCountResponse(user_id=str(user_id), unread_count=count)


@notification_routes.patch(
    "/notifications/{notification_id}/read",
    summary="Mark a notification as read",
    response_model=NotificationInfo,
    status_code=status.HTTP_200_OK,
)
async def mark_notification_as_read(
    request: Request,
    notification_id: UUID,
    notification_service: notification_service_dependency,
) -> NotificationInfo:
    """Mark a single notification as read."""
    return await notification_service.mark_as_read(notification_id=notification_id)


@notification_routes.patch(
    "/notifications/users/{user_id}/read-all",
    summary="Mark all notifications as read for a user",
    response_model=BulkMarkReadResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_all_notifications_as_read(
    request: Request,
    user_id: UUID,
    notification_service: notification_service_dependency,
) -> BulkMarkReadResponse:
    """Mark all unread notifications for a user as read."""
    result = await notification_service.mark_all_as_read(user_id=user_id)
    return BulkMarkReadResponse.model_validate(result)


@notification_routes.delete(
    "/notifications/{notification_id}",
    summary="Delete a notification",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification(
    request: Request,
    notification_id: UUID,
    notification_service: notification_service_dependency,
) -> None:
    """Delete a notification by ID."""
    await notification_service.delete_notification(notification_id=notification_id)
    return None
