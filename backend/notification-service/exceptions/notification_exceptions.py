from shared.base_exceptions import BaseAPIException


class EmailServiceError(BaseAPIException):
    """Raised when there is an error in the email service"""
    def __init__(self, detail: str = "Email service error"):
        super().__init__(detail=detail, status_code=500)

        
class EmailSendError(BaseAPIException):
    """Raised when there is an error sending the email"""
    def __init__(self, detail: str = "Email send error"):
        super().__init__(detail=detail, status_code=500)
        
class EmailTemplateError(BaseAPIException):    
    """Raised when there is an error in the email template"""
    def __init__(self, detail: str = "Email template error"):
        super().__init__(detail=detail, status_code=500)