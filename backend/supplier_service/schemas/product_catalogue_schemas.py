"""The part of product-service's product response that supplier-service reads."""

from uuid import UUID

from pydantic import BaseModel, Field


class ProductVariantLookup(BaseModel):
    id: UUID
    vid: str
    active: bool = True


class ProductWithVariants(BaseModel):
    pid: str | None = None
    variants: list[ProductVariantLookup] = Field(default_factory=list)
