from typing import Annotated, AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.notification_repository import NotificationRepository
from service_layer.notification_service import NotificationService
from resources import NotificationApiResources


def get_resources(request: Request) -> NotificationApiResources:
    return request.app.state.resources


async def get_db_session(
    resources: NotificationApiResources = Depends(get_resources),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional DB session for the notification service."""
    async with resources.database.transaction() as session:
        yield session


def get_notification_service(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationService:
    """Dependency that provides a fully wired NotificationService."""
    return NotificationService(repository=NotificationRepository(session=session))


notification_service_dependency = Annotated[NotificationService, Depends(get_notification_service)]
