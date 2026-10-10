"""What the back office sees of payment-service's tables (see shared.admin.admin_tables)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PaymentAdminSchema(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    user_email: str
    stripe_payment_intent_id: str
    # All amounts in cents.
    amount: int
    refunded_cents: int
    capture_reduction_cents: int
    currency: str
    status: str
    failure_reason: str | None
    tax_calculation_id: str | None
    tax_transaction_id: str | None
    date_created: datetime
    date_updated: datetime | None


class PaymentRefundAdminSchema(BaseModel):
    id: UUID
    payment_id: UUID
    amount_cents: int
    reason: str
    status: str
    stripe_refund_id: str | None
    failure_reason: str | None
    date_created: datetime


class PaymentDisputeAdminSchema(BaseModel):
    id: UUID
    stripe_dispute_id: str
    payment_id: UUID | None
    amount_cents: int
    currency: str
    reason: str
    status: str
    evidence_due_by: datetime | None
    date_created: datetime
    date_updated: datetime | None
