"""Order payload fragments embedded in cross-service events."""

from uuid import UUID
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat

from contracts.artwork import GeneratedArtworkAsset
from contracts.limits import Code, Count, MONEY_MAX, Name, OBJECT_KEYS_MAX, PositiveCount, Text


FulfillmentType = Literal["catalog", "cj", "custom"]


class CustomTshirtSpecification(BaseModel):
    """Immutable production snapshot for a user-generated T-shirt."""

    design_asset: GeneratedArtworkAsset
    prompt: Text
    style: Name
    size: Literal["S", "M", "L"]
    garment_color: Literal["white", "black"]
    placement: Literal[
        "Center Chest",
        "Left Top Chest",
        "Right Top Chest",
        "Left Bottom",
        "Right Bottom",
        "Center Bottom",
        "Oversized Center",
        "Full Back",
        "Back Upper",
        "Back Lower",
    ]
    gender: Literal["Male", "Female", "X"]
    # A T-shirt's print area is under 20 inches a side; the dpi follows from it.
    print_width_in: PositiveFloat | None = Field(default=None, le=100)
    print_height_in: PositiveFloat | None = Field(default=None, le=100)
    effective_dpi: PositiveFloat | None = Field(default=None, le=100_000)


class OrderItem(BaseModel):
    order_id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    quantity: PositiveCount
    price: PositiveFloat = Field(le=float(MONEY_MAX))
    fulfillment_type: FulfillmentType = "catalog"
    product_name: Name | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = Field(default=None, max_length=OBJECT_KEYS_MAX)

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderItem(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: Count
    price: PositiveFloat = Field(le=float(MONEY_MAX))
    fulfillment_type: FulfillmentType = "catalog"
    product_name: Name | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = Field(default=None, max_length=OBJECT_KEYS_MAX)

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderAddress(BaseModel):
    street: Name
    city: Name
    province: Code
    postal_code: Code
    country: Name | None = None
    country_code: Code | None = None
    name: Name | None = None
    phone: Code | None = None

    model_config = ConfigDict(from_attributes=True)
