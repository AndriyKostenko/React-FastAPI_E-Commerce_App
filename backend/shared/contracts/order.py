"""Order payload fragments embedded in cross-service events."""

from uuid import UUID

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt

from shared.contracts.artwork import GeneratedArtworkAsset


FulfillmentType = Literal["catalog", "cj", "custom"]


class CustomTshirtSpecification(BaseModel):
    """Immutable production snapshot for a user-generated T-shirt."""

    design_asset: GeneratedArtworkAsset
    prompt: str
    style: str
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
    print_width_in: PositiveFloat | None = None
    print_height_in: PositiveFloat | None = None
    effective_dpi: PositiveFloat | None = None


class OrderItem(BaseModel):
    order_id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    quantity: PositiveInt
    price: PositiveFloat
    fulfillment_type: FulfillmentType = "catalog"
    product_name: str | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderItem(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int
    price: PositiveFloat
    fulfillment_type: FulfillmentType = "catalog"
    product_name: str | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderAddress(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str
    country: str | None = None
    country_code: str | None = None
    name: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)
