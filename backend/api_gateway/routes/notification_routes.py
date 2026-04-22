from uuid import UUID

from fastapi import APIRouter, Request, Depends

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import get_current_user
from shared.utils.customized_json_response import JSONResponse
from shared.enums.services_enums import Services
from shared.schemas.user_schemas import CurrentUserInfo


notification_proxy = APIRouter(tags=["Notification Service Proxy"])


@notification_proxy.get("/notifications/users/{user_id}",
                        summary="Get all notifications for a user")
async def get_user_notifications(
    request: Request,
    user_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.NOTIFICATION_SERVICE,
    )


@notification_proxy.get("/notifications/users/{user_id}/unread-count",
                        summary="Get unread notification count for a user")
async def get_unread_count(
    request: Request,
    user_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.NOTIFICATION_SERVICE,
    )


@notification_proxy.patch("/notifications/{notification_id}/read",
                          summary="Mark a notification as read")
async def mark_notification_as_read(
    request: Request,
    notification_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.NOTIFICATION_SERVICE,
    )


@notification_proxy.patch("/notifications/users/{user_id}/read-all",
                          summary="Mark all notifications as read")
async def mark_all_notifications_as_read(
    request: Request,
    user_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.NOTIFICATION_SERVICE,
    )


@notification_proxy.delete("/notifications/{notification_id}",
                            summary="Delete a notification")
async def delete_notification(
    request: Request,
    notification_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.NOTIFICATION_SERVICE,
    )
