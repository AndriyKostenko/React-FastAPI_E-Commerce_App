from uuid import UUID

from shared.exceptions.base_exceptions import BaseAPIException

class OutboxEventCreatioError(BaseAPIException):
    """Exception raised when an outbox event could not be created in database."""
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Could not create an outbox event."
        )

class OutboxEventNotFoundError(BaseAPIException):
    """Exception raised when an outbox event/events were not found in database."""
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="An outbox event/events were not found in database"
        )

class OutboxEventUpdateError(BaseAPIException):
    """Exception raised when an outbox event was not updated in database."""
    def __init__(self, event_id: UUID) -> None:
        super().__init__(
            status_code=400,
            detail=f"An error updating an outbox event id: {event_id}"
        )
