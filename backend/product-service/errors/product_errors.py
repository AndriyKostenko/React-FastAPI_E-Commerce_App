from errors.base import BaseAPIException


#------Product Service Errors------

class ProductNotFoundError(BaseAPIException):
    """Raised when Product is not found"""
    def __init__(self, detail: str = "Product not found"):
        super().__init__(detail=detail, status_code=404)

class ProductAlreadyExistsError(BaseAPIException):
    """Raised when Product already exists"""
    def __init__(self, detail: str = "Product already exists"):
        super().__init__(detail=detail, status_code=409)

class ProductCreationError(BaseAPIException):
    """Raised when Product creation fails"""
    def __init__(self, detail: str = "Product creation failed"):
        super().__init__(detail=detail, status_code=500)

class ProductValidationError(BaseAPIException):
    """Raised when Product validation fails"""
    def __init__(self, detail: str = "Product validation failed"):
        super().__init__(detail=detail, status_code=422)

class ProductUpdateError(BaseAPIException):
    """Raised when Product update fails"""
    def __init__(self, detail: str = "Product update failed"):
        super().__init__(detail=detail, status_code=500)

class ProductDeletionError(BaseAPIException):
    """Raised when Product deletion fails"""
    def __init__(self, detail: str = "Product deletion failed"):
        super().__init__(detail=detail, status_code=500)