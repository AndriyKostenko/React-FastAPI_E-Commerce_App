from uuid import UUID

from pydantic import BaseModel, PositiveInt


class BestSellerSchema(BaseModel):
    """A product's net units sold in the ranking window."""

    product_id: UUID
    units_sold: PositiveInt
