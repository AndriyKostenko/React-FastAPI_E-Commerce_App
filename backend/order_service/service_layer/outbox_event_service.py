from uuid import UUID
from datetime import datetime, timezone

from pydantic import BaseModel

from database_layer.outbox_repository import OutboxRepository
from models.outbox_events import OutboxEvent
from exceptions.outbox_event_exceptions import OutboxEventCreatioError, OutboxEventNotFoundError, OutboxEventUpdateError


class OutboxEventService:
    def __init__(self, repository: OutboxRepository) -> None:
        self.repository: OutboxRepository = repository
        self.field_names: list[str] = OutboxEvent.get_search_fields()

    async def add_outbox_event(self, event_type: str, payload: BaseModel) -> None:
        payload_dict = payload.model_dump(mode="json")
        outbox_db_event: OutboxEvent = await self.repository.create(
            OutboxEvent(
                event_type=event_type,
                payload=payload_dict
        ))
        if not outbox_db_event:
            raise OutboxEventCreatioError()

    async def get_all_events(self) -> list[OutboxEvent]:
        outbox_db_events: list[OutboxEvent] = await self.repository.get_all()
        return outbox_db_events

    async def get_unprocessed_events(self, limit: int | None = 50) -> list[OutboxEvent]:
        unprocessed_db_events: list[OutboxEvent] = await self.repository.get_many_by_field(field_name="processed", value=False, limit=limit)
        if not unprocessed_db_events:
            raise OutboxEventNotFoundError()
        return unprocessed_db_events

    async def mark_event_as_processed(self, event_id: UUID) -> None:
        outbox_event = await self.repository.update_by_id(
            item_id=event_id,
            data={"processed": True,
                  "processed_at": datetime.now(timezone.utc)})
        if not outbox_event:
            raise OutboxEventUpdateError(event_id)

outbox_event_service = OutboxEventService(?????)