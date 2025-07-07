from typing import Any

from fastapi import HTTPException




# using Factory Pattern along with Inheritance design patterns for creating user related service errors
class BaseAPIException(HTTPException):
    """Base class for all API exceptions."""
    def __init__(self, status_code: int, detail: Any = None, headers: dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.headers = headers



class RouteNotFoundExceprion(BaseAPIException):
    def __init__(self, status_code: int, detail: str = "Route not found"):
        super().__init__(status_code=status_code, detail=detail)
        


class MethodNotAllowedException(BaseAPIException):
    def __init__(self, status_code: int, detail: str = "Method not allowed"):
        super().__init__(status_code=status_code, detail=detail)