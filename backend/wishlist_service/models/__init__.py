"""Register every wishlist-service model on the service-owned metadata."""

from .base import Base
from .wishlist_models import Wishlist, WishlistItem

__all__ = ["Base", "Wishlist", "WishlistItem"]
