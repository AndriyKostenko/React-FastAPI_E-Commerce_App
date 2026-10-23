from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field

from contracts.limits import Cents, Identifier


class PaymentSchema(BaseModel):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    amount: Cents
    # ISO 4217, as payments.currency stores it.
    currency: str = Field(min_length=3, max_length=3)
    # The Stripe Tax calculation the order was priced with; None when untaxed.
    tax_calculation_id: Identifier | None = None

    model_config = ConfigDict(from_attributes=True)


class PaymentIntentResponse(BaseModel):
    client_secret: str
    stripe_payment_intent_id: str
    payment_id: str
    order_id: str
    amount: int
    currency: str


class WebhookAckResponse(BaseModel):
    received: bool
    event_type: str
    idempotency: str | None = None


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    stripe_payment_intent_id: str
    amount: int
    currency: str
    status: str
    failure_reason: str | None = None
    date_created: datetime
    date_updated: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
