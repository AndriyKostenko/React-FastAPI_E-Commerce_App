"""Register every supplier-service model on the service-owned metadata."""

from .base import Base
from .outbox_models import OutboxEvent
from .supplier_config_models import SupplierConfig
from .supplier_sync_state_models import SupplierSyncState
from .cj_order_attempt_models import CJOrderAttempt
from .cj_stock_subscription_models import CJStockSubscription, CJStockSubscriptionVariant

__all__ = ["Base", "OutboxEvent", "SupplierConfig", "SupplierSyncState", "CJOrderAttempt",
           "CJStockSubscription", "CJStockSubscriptionVariant"]
