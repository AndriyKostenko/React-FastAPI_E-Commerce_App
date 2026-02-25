from typing import Any

from sqlalchemy.types import JSON
from database_layer.outbox_repository import OutboxRepository
from models.outbox_events import OutboxEvent


class OutboxEventService:
    def __init__(self, repository: OutboxRepository) -> None:
        self.repository: OutboxRepository = repository
        
    async def add_outbox_event(self, event_type: str, payload: JSON) -> :
        outbox_db_event: OutboxEvent = await self.repository.create(
            OutboxEvent(
                event_type=event_type,
                payload=payload
        ))
        return 
        