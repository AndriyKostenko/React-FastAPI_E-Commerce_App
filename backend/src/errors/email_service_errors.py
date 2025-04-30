class EmailServiceError(Exception):
    """Base class for all email service errors."""
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(self.detail)