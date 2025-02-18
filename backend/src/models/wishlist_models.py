from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String

from src.models import Base
from src.utils.generate_uuid import generate_uuid

class Wishlist(Base):
    __tablename__ = 'wishlists'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    date_created: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    date_updated: Mapped[datetime] = mapped_column(nullable=True)

    items: Mapped[List['WishlistItem']] = relationship('WishlistItem', back_populates='wishlist', cascade='all, delete-orphan')
    user: Mapped['User'] = relationship('User', back_populates='wishlist') # type: ignore

class WishlistItem(Base):
    __tablename__ = 'wishlist_items'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    wishlist_id: Mapped[str] = mapped_column(ForeignKey('wishlists.id'), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), nullable=False)
    date_added: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None),
        nullable=False
    )

    wishlist: Mapped['Wishlist'] = relationship('Wishlist', back_populates='items')
    product: Mapped['Product'] = relationship('Product') # type: ignore
