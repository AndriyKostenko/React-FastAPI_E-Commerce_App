"""What the back office sees of order-service's tables (see shared.admin.admin_tables)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class OrderRefundAdminSchema(BaseModel):
    """A refund, across all orders; the refunded lines are on the order's own refund list."""
    id: UUID
    order_id: UUID
    amount: Decimal
    tax_amount: Decimal
    includes_shipping: bool
    reason: str
    status: str
    requested_by: UUID | None
    return_request_id: UUID | None
    failure_reason: str | None
    settled_at: datetime | None
    date_created: datetime


class OrderItemAdminSchema(BaseModel):
    """One line of an order: what the refund form offers to give back."""
    id: UUID
    order_id: UUID
    product_id: UUID
    variant_id: UUID | None
    quantity: int
    price: Decimal
    date_created: datetime


class OrderAdminSchema(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    status: str
    delivery_status: str
    dispute_status: str | None
    amount: Decimal
    subtotal_amount: Decimal | None
    shipping_amount: Decimal | None
    tax_amount: Decimal | None
    currency: str
    shipping_logistic_name: str | None
    payment_intent_id: str | None
    cj_order_number: str | None
    date_created: datetime
    date_updated: datetime | None
