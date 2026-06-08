from shared.exceptions.base_exceptions import BaseAPIException


class ImageGenerationConfigurationError(BaseAPIException):
    def __init__(self, detail: str = "Image generation provider is not configured"):
        super().__init__(status_code=503, detail=detail)


class ImageGenerationProviderError(BaseAPIException):
    def __init__(self, detail: str = "Image generation provider request failed"):
        super().__init__(status_code=502, detail=detail)


class ImageGenerationLimitExceededError(BaseAPIException):
    def __init__(self, retry_after: int, limit: int):
        super().__init__(
            status_code=429,
            detail={
                "message": f"Guest image generation limit ({limit}) reached",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


class ImageGenerationJobNotFoundError(BaseAPIException):
    def __init__(self):
        super().__init__(status_code=404, detail="Image generation job not found or expired")
