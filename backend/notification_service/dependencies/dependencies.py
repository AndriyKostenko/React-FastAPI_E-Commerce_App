from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.notification_repository import NotificationRepository
from service_layer.notification_service import NotificationService
from shared.shared_instances import notification_service_database_session_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional DB session for the notification service."""
    async with notification_service_database_session_manager.transaction() as session:
        yield session


def get_notification_service(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationService:
    """Dependency that provides a fully wired NotificationService."""
    return NotificationService(repository=NotificationRepository(session=session))


notification_service_dependency = Annotated[NotificationService, Depends(get_notification_service)]
