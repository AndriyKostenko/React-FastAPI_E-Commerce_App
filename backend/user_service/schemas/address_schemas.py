from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.shipping_region import CanadianAddress, NotShippableError


class AddressInput(BaseModel):
    """
    A saved address as the customer submits it, to create or replace one.

    Canadian or refused with a 422, checked by the same rules order-service
    applies at checkout, so an address that can be saved can also be shipped
    to. The country, province and postal code come back normalised.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    label: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    street: str = Field(..., min_length=3, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    province: str = Field(..., min_length=2, max_length=64)
    postal_code: str = Field(..., min_length=6, max_length=10)
    country: str | None = Field(default=None, max_length=64)
    country_code: str | None = Field(default=None, max_length=2)
    is_default: bool = False

    @model_validator(mode="after")
    def _canadian(self) -> "AddressInput":
        try:
            canadian = CanadianAddress.normalise(
                country=self.country,
                country_code=self.country_code,
                province=self.province,
                postal_code=self.postal_code,
            )
        except NotShippableError as exc:
            raise ValueError(str(exc)) from exc
        self.country = canadian.country
        self.country_code = canadian.country_code
        self.province = canadian.province_code
        self.postal_code = canadian.postal_code
        # An empty phone is no phone.
        self.phone = self.phone or None
        return self


class AddressRead(BaseModel):
    id: UUID
    label: str
    name: str
    phone: str | None
    street: str
    city: str
    province: str
    postal_code: str
    country: str
    country_code: str
    is_default: bool
    date_created: datetime
    date_updated: datetime | None

    model_config = ConfigDict(from_attributes=True)
