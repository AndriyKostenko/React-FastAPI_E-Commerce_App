from typing import Annotated
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.outbox_repository import OutboxRepository
from service_layer.order_service import OrderService
from service_layer.order_item_service import OrderItemService
from service_layer.order_address_service import OrderAddressService
from service_layer.outbox_event_service import OutboxEventService
from shared.shared_instances import order_service_database_session_manager
from database_layer.order_repository import OrderRepository



async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()
    """
    async with order_service_database_session_manager.transaction() as session:
        yield session

def get_order_item_service(session: AsyncSession = Depends(get_db_session)) -> OrderItemService:
    """
    Dependency to provide an OrderItemService(for buisiness logic and data validation),
    which operates OrderItemRepository(inherits BaseRepository) for db session management.
    """
    return OrderItemService(repository=OrderItemRepository(session=session))

def get_order_address_service(session: AsyncSession = Depends(get_db_session)) -> OrderAddressService:
    """
    Dependency to provide OrderAdressService (for buisiness logic and data validation),
    which operates OrderAddressRepository(inherits BaseRepository) for db session management.
    """
    return OrderAddressService(repository=OrderAddressRepository(session=session))

def get_outbox_service(session: AsyncSession = Depends(get_db_session)) -> OutboxEventService:
    """
    Dependency to provide OutboxEventService (for buisiness logic and data validation),
    which operates OutboxRepository(inherits BaseRepository) for db session management.
    """
    return OutboxEventService(repository=OutboxRepository(session=session))

def get_order_service(session: AsyncSession = Depends(get_db_session),
                      order_item_service: OrderItemService = Depends(get_order_item_service),
                      order_address_service: OrderAddressService = Depends(get_order_address_service),
                      outbox_event_service: OutboxEventService = Depends(get_outbox_service)) -> OrderService:
    """
    Dependency to provide OrderService (for buisiness logic and data validation),
    which operates OrderRepository(inherits BaseRepository) for db session management.
    """
    return OrderService(repository=OrderRepository(session=session),
                        outbox_event_service=outbox_event_service,
                        order_item_service=order_item_service,
                        order_address_service=order_address_service)

order_address_dependency = Annotated[OrderAddressService, Depends(get_order_address_service)]
order_item_dependency = Annotated[OrderItemService, Depends(get_order_item_service)]
order_service_dependency = Annotated[OrderService, Depends(get_order_service)]
