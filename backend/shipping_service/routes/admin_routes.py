from dependencies.dependencies import get_db_session
from models.shipping_models import Shipment
from schemas.admin_schemas import ShipmentAdminSchema
from shared.admin.admin_tables import AdminTable, AdminTableRouter

# Read-only: shipments follow the order's fulfilment events.
admin_routes = AdminTableRouter(get_db_session).build([
    AdminTable("shipments", Shipment, ShipmentAdminSchema, filterable=("status", "order_id", "user_id")),
])
