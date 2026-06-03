from pydantic import BaseModel, Field


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=1000)
    style: str = Field(..., min_length=2, max_length=100)


class GenerateImageResponse(BaseModel):
    image_url: str
    model: str
    remaining_generations: int | None = None
    guest_limit: int | None = None
