from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WishlistItemSchema(BaseModel):
    id: UUID
    wishlist_id: UUID
    product_id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WishlistSchema(BaseModel):
    id: UUID
    user_id: UUID
    items: list[WishlistItemSchema]
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AddWishlistItem(BaseModel):
    product_id: UUID
