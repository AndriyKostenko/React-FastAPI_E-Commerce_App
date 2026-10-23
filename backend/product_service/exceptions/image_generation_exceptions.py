from infrastructure.exceptions.base_exceptions import BaseAPIException


class ImageGenerationConfigurationError(BaseAPIException):
    def __init__(self, detail: str = "Image generation provider is not configured"):
        super().__init__(status_code=503, detail=detail)


class ImageGenerationProviderError(BaseAPIException):
    def __init__(self, detail: str = "Image generation provider request failed"):
        super().__init__(status_code=502, detail=detail)


class ImageBackgroundRemovalError(BaseAPIException):
    """The cutout step failed or produced artwork that would not print."""

    def __init__(self, detail: str = "Background removal failed"):
        super().__init__(status_code=502, detail=detail)


class ImageGenerationLimitExceededError(BaseAPIException):
    def __init__(self, retry_after: int, limit: int):
        super().__init__(
            status_code=429,
            detail={
                "message": f"Image generation limit ({limit}) reached",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


class DesignRefusedError(BaseAPIException):
    """A moderation check refused the design; the detail names the rule broken."""

    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=detail)


class DesignCheckUnavailableError(BaseAPIException):
    """The design could not be checked, so it was not produced (fail closed)."""

    def __init__(self, detail: str = "We couldn't check your design just now. Please try again in a moment."):
        super().__init__(status_code=503, detail=detail)


class ImageGenerationJobNotFoundError(BaseAPIException):
    def __init__(self):
        super().__init__(status_code=404, detail="Image generation job not found or expired")
