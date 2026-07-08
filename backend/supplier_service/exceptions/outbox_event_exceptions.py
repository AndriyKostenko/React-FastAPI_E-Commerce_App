from uuid import UUID


class OutboxEventCreationError(Exception):
    """Raised when an outbox event cannot be created."""
    pass


class OutboxEventNotFoundError(Exception):
    """Raised when no unprocessed outbox events are found."""
    pass


class OutboxEventUpdateError(Exception):
    """Raised when an outbox event cannot be marked as processed."""
    def __init__(self, event_id: UUID):
        self.event_id = event_id
        super().__init__(f"Failed to update outbox event: {event_id}")
