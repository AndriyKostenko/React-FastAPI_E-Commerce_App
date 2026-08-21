from pydantic import BaseModel

from models.outbox_models import OutboxEvent
from shared.database_layer.outbox_repository import OutboxRepository


class OutboxEventService:
    def __init__(self, repository: OutboxRepository):
        self.repository = repository

    async def add_outbox_event(self, event_type: str, payload: BaseModel) -> OutboxEvent:
        return await self.repository.create(
            OutboxEvent(
                event_type=event_type,
                payload=payload.model_dump(mode="json"),
            )
        )

