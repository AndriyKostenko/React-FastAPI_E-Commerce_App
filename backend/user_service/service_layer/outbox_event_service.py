from uuid import UUID
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from shared.database_layer.outbox_repository import OutboxRepository
from models.outbox_models import OutboxEvent
from exceptions.outbox_event_exceptions import OutboxEventCreationError, OutboxEventUpdateError


class OutboxEventService:
    """Service for handling outbox events, such as creating an event, getting unprocessed events and marking events as processed"""
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
            raise OutboxEventCreationError()

    async def get_all_events(self) -> list[OutboxEvent]:
        outbox_db_events: list[OutboxEvent] = await self.repository.get_all()
        return outbox_db_events

    async def get_unprocessed_events(self, limit: int = 50) -> list[OutboxEvent]:
        unprocessed_db_events = await self.repository.get_pending_with_lock(limit=limit)
        return unprocessed_db_events or []

    async def mark_event_as_processed(self, event_id: UUID) -> None:
        outbox_event = await self.repository.update_by_id(
            item_id=event_id,
            data={"processed": True,
                  "processed_at": datetime.now(timezone.utc)})
        if not outbox_event:
            raise OutboxEventUpdateError(event_id)

    async def record_publish_failure(self, event_id: UUID, error: Exception) -> None:
        event = await self.repository.get_by_id(event_id)
        if not event:
            raise OutboxEventUpdateError(event_id)
        attempts = event.attempts + 1
        # Exponential retry capped at one hour; poison messages remain visible.
        retry_at = datetime.now(timezone.utc) + timedelta(seconds=min(2 ** attempts, 3600))
        updated = await self.repository.update_by_id(
            item_id=event_id,
            data={"attempts": attempts, "last_error": str(error)[:2000], "next_retry_at": retry_at},
        )
        if not updated:
            raise OutboxEventUpdateError(event_id)
