from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from shared.contracts.returns import ReturnFault, ReturnReason, ReturnStatus


class ReturnLineRequest(BaseModel):
    order_item_id: UUID
    quantity: PositiveInt


class ReturnRequestCreate(BaseModel):
    """What the customer sends (as the ``request`` form field, beside the photos)."""

    lines: list[ReturnLineRequest] = Field(min_length=1, max_length=50)
    reason: ReturnReason
    description: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def _each_line_once(self) -> "ReturnRequestCreate":
        item_ids = [line.order_item_id for line in self.lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("each line may appear once")
        return self


class ReturnDecision(BaseModel):
    """An admin's approve / receive note; a rejection must say why."""

    note: str | None = Field(default=None, max_length=1000)


class ReturnRejection(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class ReturnLine(BaseModel):
    order_item_id: UUID
    quantity: int
    ships_back: bool
    refunded: bool


class ReturnPhoto(BaseModel):
    index: int
    content_type: str
    size: int


class ReturnRequestSchema(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    reason: ReturnReason
    fault: ReturnFault
    description: str
    lines: list[ReturnLine]
    photos: list[ReturnPhoto]
    refund_shipping: bool
    status: ReturnStatus
    admin_note: str | None
    decided_by: UUID | None
    decided_at: datetime | None
    received_at: datetime | None
    date_created: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _number_photos(cls, data: object) -> object:
        """Stored photos carry a storage key; the API shows them by index only."""
        photos = getattr(data, "photos", None)
        if photos is None or isinstance(data, dict):
            return data
        return {
            **{name: getattr(data, name) for name in cls.model_fields if name != "photos"},
            "photos": [
                {"index": index, "content_type": photo["content_type"], "size": photo["size"]}
                for index, photo in enumerate(photos)
            ],
        }


class ReturnableLine(BaseModel):
    """One order line as the return form sees it."""

    order_item_id: UUID
    product_name: str
    fulfillment_type: str
    quantity: int
    returnable_quantity: int
    return_by: datetime | None
    allowed_reasons: list[ReturnReason]
    # Why the line cannot be returned right now; None when it can.
    unavailable_reason: str | None = None


class ReturnEligibility(BaseModel):
    order_id: UUID
    window_days: int
    photo_required_for: list[ReturnReason]
    lines: list[ReturnableLine]
