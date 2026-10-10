from dependencies.dependencies import get_db_session
from models.order_item_models import OrderItem
from models.order_models import Order
from models.order_refund_models import OrderRefund
from schemas.admin_schemas import OrderAdminSchema, OrderItemAdminSchema, OrderRefundAdminSchema
from shared.admin.admin_tables import AdminTable, AdminTableRouter

# Read-only: a refund is made with POST /admin/orders/{id}/refunds, which
# applies the caps and sends it to payment-service.
admin_routes = AdminTableRouter(get_db_session).build([
    # Paged and filterable, unlike GET /orders, which returns every order at once.
    AdminTable("orders", Order, OrderAdminSchema,
               filterable=("status", "delivery_status", "dispute_status", "user_id", "user_email")),
    AdminTable("refunds", OrderRefund, OrderRefundAdminSchema, filterable=("status", "order_id")),
    AdminTable("order-items", OrderItem, OrderItemAdminSchema, filterable=("order_id",)),
])
