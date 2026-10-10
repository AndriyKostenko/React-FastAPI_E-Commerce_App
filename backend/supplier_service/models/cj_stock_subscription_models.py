from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class CJStockSubscription(Base, TimestampMixin):
    """
    A CJ product we sell, and whether CJ pushes its stock changes to us.

    One row per product product-service sells; ``subscribed_at`` is set once
    CJ accepted the subscription. Kept by the hourly reconcile.
    """

    __tablename__ = "cj_stock_subscriptions"

    pid: Mapped[str] = mapped_column(String(64), primary_key=True)
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CJStockSubscriptionVariant(Base):
    """
    A variant of a product we sell -> its product.

    A STOCK push names variants only, while product-service's stock update is
    per product, so this is how a push finds its products. A variant not
    listed is one we do not sell, and its push is ignored.
    """

    __tablename__ = "cj_stock_subscription_variants"
    __table_args__ = (Index("idx_cj_stock_subscription_variants_pid", "pid"),)

    vid: Mapped[str] = mapped_column(String(64), primary_key=True)
    pid: Mapped[str] = mapped_column(
        String(64), ForeignKey("cj_stock_subscriptions.pid", ondelete="CASCADE"), nullable=False
    )
