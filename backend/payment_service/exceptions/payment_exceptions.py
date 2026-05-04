from uuid import UUID

from shared.exceptions.base_exceptions import BaseAPIException


class PaymentNotFoundError(BaseAPIException):
    def __init__(self, payment_id: UUID | str) -> None:
        super().__init__(
            status_code=404,
            detail=f"Payment with ID: {payment_id} is not found."
        )


class PaymentsNotFoundError(BaseAPIException):
    def __init__(self) -> None:
        super().__init__(status_code=404, detail="Payments not found.")


class DuplicatePaymentIntentError(BaseAPIException):
    def __init__(self, payment_intent_id: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Payment with payment_intent_id '{payment_intent_id}' already exists."
        )


class PaymentCreationError(BaseAPIException):
    def __init__(self, detail: str = "Failed to create payment record.") -> None:
        super().__init__(status_code=500, detail=detail)


class InvalidStripeWebhookSignature(BaseAPIException):
    def __init__(self) -> None:
        super().__init__(status_code=400, detail="Invalid Stripe webhook signature.")


class StripePaymentIntentCreationError(BaseAPIException):
    def __init__(self, detail: str = "Failed to create Stripe PaymentIntent.") -> None:
        super().__init__(status_code=502, detail=detail)


class PaymentRefundError(BaseAPIException):
    def __init__(self, detail: str = "Failed to issue Stripe refund.") -> None:
        super().__init__(status_code=502, detail=detail)
