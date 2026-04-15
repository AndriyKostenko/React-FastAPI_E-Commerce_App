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


class NotificationNotFoundError(BaseAPIException):
    """Raised when a notification is not found"""
    def __init__(self, detail: str = "Notification not found"):
        super().__init__(detail=detail, status_code=404)


class NotificationAccessDeniedError(BaseAPIException):
    """Raised when a user tries to access another user's notification"""
    def __init__(self, detail: str = "Access denied to this notification"):
        super().__init__(detail=detail, status_code=403)
