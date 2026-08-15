"""Minimal product API response contract consumed by supplier-service."""

from uuid import UUID

from pydantic import BaseModel, Field


class ProductVariantLookup(BaseModel):
    id: UUID
    vid: str


class ProductWithVariants(BaseModel):
    pid: str | None = None
    variants: list[ProductVariantLookup] = Field(default_factory=list)
