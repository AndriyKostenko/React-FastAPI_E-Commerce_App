from enum import Enum

from pydantic import BaseModel, Field


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=1000)
    style: str = Field(..., min_length=2, max_length=100)


class GenerateImageResponse(BaseModel):
    image_url: str
    model: str
    remaining_generations: int | None = None
    guest_limit: int | None = None


class ImageJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ImageGenerationJobSubmitResponse(BaseModel):
    """Returned immediately (202) when a generation job is accepted."""
    job_id: str
    status: ImageJobStatus
    remaining_generations: int | None = None
    guest_limit: int | None = None


class ImageGenerationJobStatusResponse(BaseModel):
    """Returned by the status-poll endpoint."""
    job_id: str
    status: ImageJobStatus
    image_url: str | None = None
    model: str | None = None
    error: str | None = None
