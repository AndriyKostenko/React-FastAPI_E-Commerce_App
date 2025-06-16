from errors.base import BaseAPIException

#------Review Service Errors------
class ReviewNotFoundError(BaseAPIException):
    """Raised when a Review is not found"""
    def __init__(self, detail: str = "Review not found"):
        super().__init__(detail=detail, status_code=404)
        
        
class ReviewAlreadyExistsError(BaseAPIException):
    """Raised when a Review already exists"""
    def __init__(self, detail: str = "Review already exists"):
        super().__init__(detail=detail, status_code=409)
        
        
class ReviewCreationError(BaseAPIException):
    """Raised when there is an error creating a Review"""
    def __init__(self, detail: str = "Error creating Review"):
        super().__init__(detail=detail, status_code=500)
        
        
class ReviewUpdateError(BaseAPIException):
    """Raised when there is an error updating a Review"""
    def __init__(self, detail: str = "Error updating Review"):
        super().__init__(detail=detail, status_code=500)
        
        
class ReviewDeletionError(BaseAPIException):
    """Raised when there is an error deleting a Review"""
    def __init__(self, detail: str = "Error deleting Review"):
        super().__init__(detail=detail, status_code=500)