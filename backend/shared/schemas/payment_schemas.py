from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict


class PaymentSchema(BaseModel):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    amount: int  # in cents
    currency: str

    model_config = ConfigDict(from_attributes=True)


class PaymentIntentResponse(BaseModel):
    client_secret: str
    stripe_payment_intent_id: str
    payment_id: str
    order_id: str


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
