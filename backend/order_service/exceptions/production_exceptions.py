from uuid import UUID

from shared.exceptions.base_exceptions import BaseAPIException


class ProductionJobNotFoundError(BaseAPIException):
    """Exception raised when a production job is not on the queue."""
    def __init__(self, job_id: UUID) -> None:
        super().__init__(
            status_code=404,
            detail=f"Production job with ID: {job_id} is not found."
        )


class InvalidProductionTransitionError(BaseAPIException):
    """Exception raised when a queue action does not fit the job's current state."""
    def __init__(self, job_id: UUID, current: str, target: str) -> None:
        super().__init__(
            status_code=409,
            detail=(
                f"Production job {job_id} cannot move from '{current}' to "
                f"'{target}'."
            ),
        )


class ProductionArtworkUnavailableError(BaseAPIException):
    """Exception raised when the print file behind a job cannot be served.

    Either the job carries no generated design, or product_service refused the
    stored manifest — both mean the operator must not print from it.
    """
    def __init__(self, job_id: UUID, reason: str) -> None:
        super().__init__(
            status_code=422,
            detail=f"Print artwork for production job {job_id} is unavailable: {reason}",
        )
