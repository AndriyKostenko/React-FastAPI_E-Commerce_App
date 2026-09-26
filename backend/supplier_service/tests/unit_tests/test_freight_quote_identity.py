"""The freight-quote route is order-service's alone: its guard is attached."""

from shared.auth.service_assertion import ServiceCallerGuard
from routes.supplier_routes import supplier_routes


def test_freight_quote_requires_order_services_signature() -> None:
    route = next(r for r in supplier_routes.routes if getattr(r, "path", "").endswith("/cjdropshipping/freight/quote"))
    guards = [d.call for d in route.dependant.dependencies if isinstance(d.call, ServiceCallerGuard)]
    assert guards and guards[0]._allowed == ("order-service",)
