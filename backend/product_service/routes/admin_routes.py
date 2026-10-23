from dependencies.dependencies import get_db_session
from models.design_moderation_refusal_models import DesignModerationRefusal
from schemas.design_moderation_schemas import DesignRefusalAdminSchema
from infrastructure.admin.admin_tables import AdminTable, AdminTableRouter

# Read-only: the generation job writes a refusal; nobody edits one.
admin_routes = AdminTableRouter(get_db_session).build([
    AdminTable("design-refusals", DesignModerationRefusal, DesignRefusalAdminSchema,
               filterable=("stage", "category", "user_id")),
])
