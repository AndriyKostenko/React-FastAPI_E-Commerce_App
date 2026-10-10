from dependencies.dependencies import get_db_session
from models.payment_models import Payment, PaymentDispute, PaymentRefund
from schemas.admin_schemas import PaymentAdminSchema, PaymentDisputeAdminSchema, PaymentRefundAdminSchema
from shared.admin.admin_tables import AdminTable, AdminTableRouter

# Read-only: money moves only through refunds order-service requests and
# through Stripe; disputes are answered in the Stripe dashboard.
admin_routes = AdminTableRouter(get_db_session).build([
    AdminTable("payments", Payment, PaymentAdminSchema, filterable=("status", "order_id", "user_id")),
    AdminTable("payment-refunds", PaymentRefund, PaymentRefundAdminSchema, filterable=("status", "payment_id")),
    AdminTable("disputes", PaymentDispute, PaymentDisputeAdminSchema, filterable=("status", "payment_id")),
])
