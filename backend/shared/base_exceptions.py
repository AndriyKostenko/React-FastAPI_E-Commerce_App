from typing import Any, Dict, Optional

from fastapi import HTTPException


# using Factory Pattern along with Inheritance design patterns for creating user related service errors
class BaseAPIException(HTTPException):
    """Base class for all API exceptions."""
    def __init__(self, status_code: int, detail: Any = None, headers: Dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.headers = headers


class RateLimitExceededError(BaseAPIException):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, client_ip: str, retry_after: int, status_code: int = 429):
        detail = {
            "message": f"Too many requests from: {client_ip}",
            "retry_after": retry_after
        }
        headers = {"Retry-After": str(retry_after)}
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers
        )