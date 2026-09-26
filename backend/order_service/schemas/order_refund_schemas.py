from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class RefundLineRequest(BaseModel):
    order_item_id: UUID
    quantity: PositiveInt


class RefundRequest(BaseModel):
    """What an admin gives back: some lines (and quantities), maybe shipping."""
    lines: list[RefundLineRequest] = Field(default_factory=list, max_length=50)
    include_shipping: bool = False
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _something_to_refund(self) -> "RefundRequest":
        if not self.lines and not self.include_shipping:
            raise ValueError("choose at least one line or the shipping")
        item_ids = [line.order_item_id for line in self.lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("each line may appear once")
        return self


class RefundLine(BaseModel):
    order_item_id: UUID
    quantity: int
    amount: Decimal


class OrderRefundSchema(BaseModel):
    id: UUID
    order_id: UUID
    amount: Decimal
    tax_amount: Decimal = Decimal("0")
    includes_shipping: bool
    lines: list[RefundLine]
    reason: str
    status: str
    requested_by: UUID | None
    failure_reason: str | None
    settled_at: datetime | None
    date_created: datetime

    model_config = ConfigDict(from_attributes=True)
