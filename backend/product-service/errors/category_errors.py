from errors.base import BaseAPIException

#------Category Service Errors------
class CategoryNotFoundError(BaseAPIException):
    """Raised when Category is not found"""
    def __init__(self, detail: str = "Category not found"):
        super().__init__(detail=detail, status_code=404)
        
        
class CategoryAlreadyExistsError(BaseAPIException):
    """Raised when Category already exists"""
    def __init__(self, detail: str = "Category already exists"):
        super().__init__(detail=detail, status_code=409)
        
        
class CategoryCreationError(BaseAPIException):
    """Raised when there is an error creating a Category"""
    def __init__(self, detail: str = "Error creating Category"):
        super().__init__(detail=detail, status_code=500)
        
        
class CategoryUpdateError(BaseAPIException):
    """Raised when there is an error updating a Category"""
    def __init__(self, detail: str = "Error updating Category"):
        super().__init__(detail=detail, status_code=500)
        
        
class CategoryDeletionError(BaseAPIException):
    """Raised when there is an error deleting a Category"""
    def __init__(self, detail: str = "Error deleting Category"):
        super().__init__(detail=detail, status_code=500)