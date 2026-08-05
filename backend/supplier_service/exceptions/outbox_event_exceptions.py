from shared.exceptions.base_exceptions import BaseAPIException


class OutboxEventCreationError(BaseAPIException):
    """Raised when an outbox event cannot be created."""
    def __init__(self, detail: str = "Outbox event creation failed."):
        super().__init__(status_code=500, detail=detail)


class OutboxEventNotFoundError(BaseAPIException):
    """Raised when no unprocessed outbox events are found."""
    def __init__(self, detail: str = "Outbox event not found."):
        super().__init__(status_code=404, detail=detail)


class OutboxEventUpdateError(BaseAPIException):
    """Raised when an outbox event cannot be marked as processed."""
    def __init__(self, detail: str = "Outbox event update failed."):
        super().__init__(status_code=500, detail=detail)
