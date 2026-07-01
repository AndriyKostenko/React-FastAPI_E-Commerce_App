"""Schemas for CJ Dropshipping API integration."""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CJProductsFilterParams(BaseModel):
    """Query parameters for CJ Dropshipping /product/listV2 endpoint.

    Reference: https://developers.cjdropshipping.cn/en/api/api2/api/product.html
    """

    # Pagination
    page: int = Field(default=1, ge=1, le=1000)
    size: int = Field(default=10, ge=1, le=100)

    # Search
    keyWord: str | None = Field(default=None, max_length=200)

    # Category filters
    categoryId: str | None = Field(default=None, max_length=200)
    lv2categoryList: list[str] | None = None
    lv3categoryList: list[str] | None = None

    # Country / warehouse
    countryCode: str | None = Field(default=None, max_length=200)
    isWarehouse: bool | None = None
    verifiedWarehouse: Literal[0, 1, 2] | None = None

    # Price range
    startSellPrice: Decimal | None = Field(default=None, ge=0)
    endSellPrice: Decimal | None = Field(default=None, ge=0)

    # Inventory range
    startWarehouseInventory: int | None = Field(default=None, ge=0)
    endWarehouseInventory: int | None = Field(default=None, ge=0)

    # Product flags
    addMarkStatus: Literal[0, 1] | None = None
    productType: int | None = None
    productFlag: Literal[0, 1, 2, 3] | None = None
    supplierId: str | None = Field(default=None, max_length=200)
    hasCertification: Literal[0, 1] | None = None
    isSelfPickup: Literal[0, 1] | None = None
    customization: Literal[0, 1] | None = None

    # Time range (milliseconds)
    timeStart: int | None = None
    timeEnd: int | None = None

    # Platform suggestion
    zonePlatform: str | None = Field(default=None, max_length=200)

    # Sorting
    sort: Literal["desc", "asc"] | None = None
    orderBy: Literal[0, 1, 2, 3, 4] | None = None

    # Optional feature flags
    features: list[
        Literal[
            "enable_description",
            "enable_category",
            "enable_combine",
            "enable_video",
        ]
    ] | None = None
