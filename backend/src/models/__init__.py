from sqlalchemy.orm import DeclarativeBase
from passlib.context import CryptContext

# Base class for all models
class Base(DeclarativeBase):
    pass

from .product_models import Product
from .order_models import Order, OrderAddress
from .cart_models import Cart
from .wishlist_models import Wishlist
from .payment_models import Payment
from .shipping_models import Shipping
from .notification_models import Notification
from .review_models import ProductReview
from .user_models import User
from .category_models import ProductCategory

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
