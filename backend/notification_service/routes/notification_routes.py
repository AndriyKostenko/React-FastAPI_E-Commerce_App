from uuid import UUID

from fastapi.responses import JSONResponse
from fastapi import APIRouter, status, Request, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from shared.shared_instances import notification_service_redis_manager
from shared.shared_instances import settings


notification_routes = APIRouter(tags=["notification-service"])

@notification_routes.get("/notifications/{user_id}",
                         summary="Get all notifications for a user")
@notification_service_redis_manager.ratelimiter(times=30, seconds=60)
async def get_user_notifications(request: Request,
                                 user_id: UUID,
                                 db) -> JSONResponse:
    """Retrieve all notifications for a given user"""
    ...


@notification_routes.patch("/notifications/{notification_id}/read",
                            summary="Mark a notification as read")
async def mark_notification_as_read(request: Request,
                                    notification_id: UUID,
                                    db) -> JSONResponse:
    """Mark a single notification as read"""
    ...


@notification_routes.delete("/notifications/{notification_id}",
                             summary="Delete a notification")
async def delete_notification(request: Request,
                               notification_id: UUID,
                               db) -> JSONResponse:
    """Delete a notification"""
    ...
