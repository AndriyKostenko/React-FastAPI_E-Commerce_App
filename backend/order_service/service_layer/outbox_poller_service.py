from uuid import UUID
from typing import Any

from orjson import loads

from exceptions.outbox_event_exceptions import OutboxEventNotFoundError
from service_layer.outbox_event_service import outbox_event_service, OutboxEventService
from events_publisher.order_event_publisher import order_event_publisher, OrderEventPublisher

class OutboxPollerService:
    def __init__(self) -> None:
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.order_event_publisher: OrderEventPublisher = order_event_publisher

    async def event_type_to_publisher(self, event_data: dict[str, Any]):
        event_type = event_data.get("event_type")
        match event_type:
            case "order.created":
                self.order_event_publisher.publish_order_created(order_id=event_data.order_id)
            case 

    async def poll_and_publish(self) -> None:
        try:
            unprocessed_events = await self.outbox_event_service.get_unprocessed_events()
        except OutboxEventNotFoundError:
            # nothing to process
            return

        for event in unprocessed_events:
            try:
                await self.event_type_to_publisher(event_data=loads(event.payload))
                await self.outbox_event_service.mark_event_as_processed(event_id=event.id)
