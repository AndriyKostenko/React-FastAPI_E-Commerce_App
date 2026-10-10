from dependencies.dependencies import get_db_session
from models.notification_models import Notification
from schemas.admin_schemas import NotificationAdminSchema
from shared.admin.admin_tables import AdminTable, AdminTableRouter

# Read-only: what was sent to whom, for answering "did I get an email?".
admin_routes = AdminTableRouter(get_db_session).build([
    AdminTable("notifications", Notification, NotificationAdminSchema,
               filterable=("user_id", "notification_type", "is_read")),
])
