from uuid import UUID
from datetime import datetime, timezone

from pydantic import BaseModel

from shared.database_layer.outbox_repository import OutboxRepository
from shared.models.outbox_events import OutboxEvent
from exceptions.outbox_event_exceptions import (
    OutboxEventCreatioError,
    OutboxEventNotFoundError,
    OutboxEventUpdateError,
)


class OutboxEventService:
    """Service for managing outbox events: create, query unprocessed, mark as processed."""
    def __init__(self, repository: OutboxRepository) -> None:
        self.repository: OutboxRepository = repository
        self.field_names: list[str] = OutboxEvent.get_search_fields()

    async def add_outbox_event(self, event_type: str, payload: BaseModel) -> None:
        payload_dict = payload.model_dump(mode="json")
        outbox_db_event: OutboxEvent = await self.repository.create(
            OutboxEvent(event_type=event_type, payload=payload_dict)
        )
        if not outbox_db_event:
            raise OutboxEventCreatioError()

    async def get_unprocessed_events(self, limit: int = 50) -> list[OutboxEvent]:
        unprocessed: list[OutboxEvent] | None = await self.repository.get_many_by_field(
            field_name="processed", value=False, limit=limit
        )
        if not unprocessed:
            raise OutboxEventNotFoundError()
        return unprocessed

    async def mark_event_as_processed(self, event_id: UUID) -> None:
        updated = await self.repository.update_by_id(
            item_id=event_id,
            data={"processed": True, "processed_at": datetime.now(timezone.utc)},
        )
        if not updated:
            raise OutboxEventUpdateError(event_id)
