"""
The back office's read-only tables (shared.admin.admin_tables), proxied.

Each service builds GET /admin/<table>, /admin/<table>/{id} and
/admin/schema/<table> for its own tables; this maps every table to its
service, behind the admin check. Literal paths, one set per table: nothing
under /admin is forwarded that is not listed here.
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from dependencies.auth_dependencies import require_admin
from resources import api_gateway_manager
from shared.enums.services_enums import Services

ADMIN_TABLES: dict[str, Services] = {
    "payments": Services.PAYMENT_SERVICE,
    "payment-refunds": Services.PAYMENT_SERVICE,
    "disputes": Services.PAYMENT_SERVICE,
    "orders": Services.ORDER_SERVICE,
    "refunds": Services.ORDER_SERVICE,
    "order-items": Services.ORDER_SERVICE,
    "cj-orders": Services.SUPPLIER_SERVICE,
    "supplier-syncs": Services.SUPPLIER_SERVICE,
    "supplier-configs": Services.SUPPLIER_SERVICE,
    "shipments": Services.SHIPPING_SERVICE,
    "notifications": Services.NOTIFICATION_SERVICE,
}

admin_table_proxy = APIRouter(tags=["Admin tables"], dependencies=[Depends(require_admin)])


def _forward_to(service: Services) -> Callable[[Request], Awaitable[Response]]:
    async def forward(request: Request) -> Response:
        return await api_gateway_manager.forward_request(service_name=service, request=request)
    return forward


for _table, _service in ADMIN_TABLES.items():
    admin_table_proxy.add_api_route(f"/admin/{_table}", _forward_to(_service), methods=["GET"],
                                    summary=f"List {_table} (admin)")
    admin_table_proxy.add_api_route(f"/admin/schema/{_table}", _forward_to(_service), methods=["GET"],
                                    summary=f"AdminJS fields of {_table}")
    admin_table_proxy.add_api_route(f"/admin/{_table}/{{record_id}}", _forward_to(_service), methods=["GET"],
                                    summary=f"One {_table} record (admin)")

# The one writable table: pause/resume a supplier's sync, change its interval.
admin_table_proxy.add_api_route("/admin/supplier-configs/{record_id}", _forward_to(Services.SUPPLIER_SERVICE),
                                methods=["PATCH"], summary="Update a supplier config (admin)")
