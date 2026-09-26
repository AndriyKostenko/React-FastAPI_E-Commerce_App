"""
Shared pytest fixtures for order_service unit and integration tests.

Unit-test fixtures replace all external dependencies (DB, RabbitMQ, Redis)
with mocks so the tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(ORDER_SERVICE_TEST_DB) and truncate all tables between tests.
"""
import os

# Tests never call the Bank of Canada: prices use the configured rate.
os.environ.setdefault("CJ_FX_SOURCE", "fixed")
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.order_repository import OrderRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_address_repository import OrderAddressRepository
from dependencies.dependencies import (
    get_db_session,
    get_fulfillment_status_service,
    get_order_service,
    get_order_item_service,
    get_order_address_service,
    get_outbox_service,
    get_production_queue_service,
)
from service_layer.order_service import OrderService
from service_layer.order_item_service import OrderItemService
from service_layer.order_address_service import OrderAddressService
from service_layer.outbox_event_service import OutboxEventService
from service_layer.artwork_asset_client import ArtworkDownload
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from service_layer.order_pricing_service import (
    CanonicalOrderQuote,
    OrderPricingService,
    QuotedOrderLine,
)
from service_layer.packing_slip_service import PackingSlipBuilder
from service_layer.production_queue_service import ProductionQueueService
from database_layer.order_fulfillment_repository import (
    CustomProductionJobRepository,
    OrderLineFulfillmentRepository,
)
from shared.database_layer.outbox_repository import OutboxRepository
from models.base import Base
from models.order_address_models import OrderAddress
from models.order_item_models import OrderItem
from models.order_models import Order
from models.outbox_models import OutboxEvent
from config import logger, settings
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from tests.constants import (
    TEST_ORDER_ID,
    TEST_ORDER_ITEM_ID,
    TEST_ORDER_ADDRESS_ID,
    TEST_USER_ID,
    TEST_PRODUCT_ID,
    TEST_PAYMENT_INTENT_ID,
    TEST_DATETIME,
    TEST_EMAIL,
    TEST_AMOUNT,
    TEST_CURRENCY,
    MOCK_ORDER_RESULT,
)


from shared.testing.helpers import allow_testserver_host
from shared.settings import get_settings
from schemas.order_schemas import OrderSchema
from shared.testing.signing_keys import EphemeralSigningKeys
from database_layer.order_refund_repository import OrderRefundRepository
from service_layer.order_refund_service import OrderRefundService
from database_layer.order_saga_repository import OrderSagaRepository

# Throwaway gateway keys: the test clients' apps trust assertions signed
# with these, exactly as a deployed service trusts the gateway's.
SIGNING_KEYS = EphemeralSigningKeys()
# Test clients call as a signed-in admin by default, so tests about business
# logic are not tripped by authorisation. Authorisation has its own tests,
# which pass an explicit per-request `auth=` (anonymous, owner, stranger).
DEFAULT_CALLER = SIGNING_KEYS.caller_auth(
    user_id=UUID("00000000-0000-4000-8000-00000000ad01"),
    role=get_settings().SECRET_ROLE,
    email="admin@example.com",
)


# ---------------------------------------------------------------------------
# Host-validation bypass for ASGI test client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _allow_testserver_host() -> None:
    """Make the default httpx/TestClient host ('testserver') pass host checks."""
    allow_testserver_host()


@pytest.fixture(scope="session")
async def test_database_session_manager(
) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    """Own and close the order test database manager for this session."""
    manager = TestDatabaseSessionManager(
        database_url=settings.ORDER_SERVICE_TEST_DATABASE_URL,
        logger=logger,
    )
    try:
        yield manager
    finally:
        await manager.close()


# ---------------------------------------------------------------------------
# Async context manager helper
# ---------------------------------------------------------------------------

class _AsyncContextManagerMock:
    """Helper for mocking `async with repo.session.begin_nested()`."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# ORM mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_order_orm() -> MagicMock:
    """Fake SQLAlchemy Order ORM object with all required attributes."""
    order = MagicMock()
    order.id = TEST_ORDER_ID
    order.user_id = TEST_USER_ID
    order.user_email = TEST_EMAIL
    order.amount = TEST_AMOUNT
    order.subtotal_amount = None
    order.shipping_amount = None
    order.tax_amount = None
    order.dispute_status = None
    order.tax_calculation_id = None
    order.shipping_logistic_name = None
    order.shipping_cost_usd = None
    order.currency = TEST_CURRENCY
    order.status = OrderStatus.PENDING
    order.delivery_status = OrderDeliveryStatus.PENDING
    order.payment_intent_id = TEST_PAYMENT_INTENT_ID
    order.address_id = TEST_ORDER_ADDRESS_ID
    order.cj_order_number = None
    order.date_created = TEST_DATETIME
    order.date_updated = None
    return order


@pytest.fixture
def mock_order_item_orm() -> MagicMock:
    """Fake SQLAlchemy OrderItem ORM object."""
    item = MagicMock()
    item.id = TEST_ORDER_ITEM_ID
    item.order_id = TEST_ORDER_ID
    item.product_id = TEST_PRODUCT_ID
    item.variant_id = None
    item.quantity = 2
    item.price = 49.99
    return item


@pytest.fixture
def mock_order_address_orm() -> MagicMock:
    """Fake SQLAlchemy OrderAddress ORM object."""
    address = MagicMock()
    address.id = TEST_ORDER_ADDRESS_ID
    address.user_id = TEST_USER_ID
    address.street = "123 Test St"
    address.city = "Testville"
    address.province = "TS"
    address.postal_code = "T1T 1T1"
    address.country = "Canada"
    address.country_code = "CA"
    address.name = "Test User"
    address.phone = "+1234567890"
    return address


# ---------------------------------------------------------------------------
# Repository mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_order_repository() -> MagicMock:
    """Mock OrderRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.get_with_fulfillment = AsyncMock()
    repo.create = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.update = AsyncMock(side_effect=lambda order: order)
    repo.delete_by_id = AsyncMock()
    repo.session = MagicMock()
    repo.session.begin_nested = MagicMock(return_value=_AsyncContextManagerMock())
    return repo


@pytest.fixture
def mock_order_item_repository() -> MagicMock:
    """Mock OrderItemRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create_many = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.get_by_order_id_with_fulfillment = AsyncMock()
    repo.session = MagicMock()
    return repo


@pytest.fixture
def mock_order_address_repository() -> MagicMock:
    """Mock OrderAddressRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_outbox_repository() -> MagicMock:
    """Mock OutboxRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.update_by_id = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Service fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_outbox_event_service(mock_outbox_repository: MagicMock) -> OutboxEventService:
    """OutboxEventService wired with a mocked repository."""
    return OutboxEventService(repository=mock_outbox_repository)


@pytest.fixture
def mock_order_item_service(mock_order_item_repository: MagicMock) -> OrderItemService:
    """OrderItemService wired with a mocked repository."""
    fulfillment_repository = MagicMock()
    fulfillment_repository.create_many = AsyncMock(side_effect=lambda rows: rows)
    return OrderItemService(
        repository=mock_order_item_repository,
        fulfillment_repository=fulfillment_repository,
    )


@pytest.fixture
def mock_order_address_service(mock_order_address_repository: MagicMock) -> OrderAddressService:
    """OrderAddressService wired with a mocked repository."""
    return OrderAddressService(repository=mock_order_address_repository)


@pytest.fixture
def order_service_unit(
    mock_order_repository: MagicMock,
    mock_order_item_service: OrderItemService,
    mock_order_address_service: OrderAddressService,
    mock_outbox_event_service: OutboxEventService,
) -> OrderService:
    """OrderService wired with all mocked dependencies."""
    pricing_service = MagicMock()
    pricing_service.build_quote = AsyncMock(
        return_value=CanonicalOrderQuote(
            items=[
                QuotedOrderLine(
                    product_id=TEST_PRODUCT_ID,
                    product_name="Widget",
                    quantity=2,
                    unit_price="49.99",
                    fulfillment_type="catalog",
                )
            ],
            subtotal_amount="99.98",
            total_amount="99.98",
        )
    )
    saga_repository = MagicMock()
    saga_repository.create = AsyncMock()
    saga = MagicMock(
        inventory_status="pending",
        payment_status="pending",
        fulfillment_status="pending",
        cancellation_reason=None,
        version=0,
    )
    saga_repository.get_for_update = AsyncMock(return_value=saga)
    saga_repository.update = AsyncMock()
    production_repository = MagicMock()
    production_repository.get_many_by_field = AsyncMock(return_value=[])
    production_repository.update = AsyncMock()
    # No lines have moved: the order-level delivery status is derived from
    # them, so an empty set leaves the stored status untouched.
    fulfillment_status_service = MagicMock()
    fulfillment_status_service.get_lines = AsyncMock(return_value=[])
    fulfillment_status_service.mark_lines = AsyncMock(
        side_effect=lambda order, *args, **kwargs: order
    )
    fulfillment_status_service.refresh_delivery_status = AsyncMock(
        side_effect=lambda order, *args, **kwargs: order
    )
    fulfillment_status_service.has_blocking_lines = AsyncMock(return_value=False)
    return OrderService(
        repository=mock_order_repository,
        order_item_service=mock_order_item_service,
        order_address_service=mock_order_address_service,
        outbox_event_service=mock_outbox_event_service,
        pricing_service=pricing_service,
        saga_repository=saga_repository,
        production_repository=production_repository,
        fulfillment_status_service=fulfillment_status_service,
    )


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_route_order_service() -> MagicMock:
    """Full mock of OrderService for app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_order = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.get_orders = AsyncMock(return_value=[MOCK_ORDER_RESULT])
    # The real method returns an OrderSchema; routes now read its user_id.
    svc.get_order_by_id = AsyncMock(return_value=OrderSchema.model_validate(MOCK_ORDER_RESULT))
    svc.get_orders_by_user_id = AsyncMock(return_value=[MOCK_ORDER_RESULT])
    svc.update_order = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.cancel_order = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.delete_order_by_id = AsyncMock(return_value=None)
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan to avoid DB/Redis/RabbitMQ connections during tests."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_order_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.
    Replaces the FastAPI lifespan with a no-op and overrides the order service.
    """
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_order_service] = lambda: mock_route_order_service

    SIGNING_KEYS.install_verifier(app)
    async with AsyncClient(transport=ASGITransport(app=app), auth=DEFAULT_CALLER, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Integration-test fixtures (real DB + real services)
# ---------------------------------------------------------------------------

class _StubCatalogQuoteClient:
    """Stands in for product_service when quoting catalog and CJ lines.

    product_service is the authority on catalog pricing and fulfillment type,
    so the stub answers as it would: it echoes the requested quantity and
    prices each line server-side, ignoring whatever the client sent.
    """

    CATALOG_UNIT_PRICE = Decimal("49.99")

    def __init__(self) -> None:
        # Products the catalog reports as CJ-fulfilled. A test adds an id here
        # to exercise the dropshipping branch without a live product_service.
        self.cj_product_ids: set[str] = set()

    async def quote(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "items": [
                {
                    "product_id": item["product_id"],
                    "variant_id": item["variant_id"],
                    "product_name": "Test product",
                    "quantity": item["quantity"],
                    "unit_price": self.CATALOG_UNIT_PRICE,
                    "fulfillment_type": (
                        "cj"
                        if item["product_id"] in self.cj_product_ids
                        else "catalog"
                    ),
                    "supplier_id": (
                        "cjdropshipping"
                        if item["product_id"] in self.cj_product_ids
                        else None
                    ),
                }
                for item in items
            ]
        }


class _StubFreightQuoteClient:
    """Stands in for supplier_service's CJ freight quote.

    Offers a cheap and a fast option, cheapest first, as the real endpoint does.
    """

    OPTIONS = [
        {"logistic_name": "CJPacket Ordinary", "price": "5.00", "delivery_time": "10-20"},
        {"logistic_name": "CJPacket Express", "price": "12.00", "delivery_time": "5-8"},
    ]

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def quote(
        self, country_code: str, postal_code: str | None, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {"country_code": country_code, "postal_code": postal_code, "items": items}
        )
        return [dict(option) for option in self.OPTIONS]


class _StubArtworkAssetClient:
    """Stands in for product_service when resolving a stored print file.

    product_service owns the artwork object, so the real client only exchanges
    a signed manifest for a URL. The stub answers the same way, which keeps
    the manifest itself — the part order_service is responsible for storing
    and presenting intact — under test.
    """

    def __init__(self) -> None:
        self.requested_keys: list[str] = []
        # Runs while the "HTTP call" is in flight, to observe what the caller
        # is holding at that moment (e.g. database connections).
        self.during_call: Callable[[], Awaitable[None]] | None = None

    async def get_download(self, asset) -> ArtworkDownload:
        self.requested_keys.append(asset.key)
        if self.during_call is not None:
            await self.during_call()
        return ArtworkDownload(
            download_url=f"/media/{asset.key}",
            filename=asset.key.rsplit("/", 1)[-1],
            sha256=asset.sha256,
            content_type="image/png",
            expires_in_seconds=3600,
        )


@pytest.fixture
def artwork_client_stub() -> _StubArtworkAssetClient:
    """The product_service stand-in used by `integration_client` for artwork."""
    return _StubArtworkAssetClient()


@pytest.fixture
def catalog_quote_stub() -> _StubCatalogQuoteClient:
    """The product_service stand-in used by `integration_client`.

    Request it alongside `integration_client` to declare what the catalog says
    about a product, e.g. that it is CJ-fulfilled.
    """
    return _StubCatalogQuoteClient()


@pytest.fixture
async def integration_client(
    test_database_session_manager: TestDatabaseSessionManager,
    catalog_quote_stub: "_StubCatalogQuoteClient",
    artwork_client_stub: "_StubArtworkAssetClient",
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (order_service TEST database)
      - OrderService, OrderItemService, OrderAddressService, OutboxEventService

    What is mocked:
      - FastAPI lifespan (tables created directly via init_db)

    Isolation:
      - Before yield: init schema (idempotent)
      - After  yield: TRUNCATE all tables
    """
    # Integration databases can outlive model changes. Rebuild this service's
    # test-only schema so create_all() cannot leave stale columns behind.
    await test_database_session_manager.recreate_schema(Base.metadata)

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_database_session_manager.transaction() as session:
            yield session

    def _override_get_order_item_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OrderItemService:
        return OrderItemService(repository=OrderItemRepository(session=session))

    def _override_get_order_address_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OrderAddressService:
        return OrderAddressService(repository=OrderAddressRepository(session=session))

    def _override_get_outbox_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OutboxEventService:
        return OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent))

    def _override_get_fulfillment_status_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OrderFulfillmentStatusService:
        return OrderFulfillmentStatusService(
            order_repository=OrderRepository(session=session),
            fulfillment_repository=OrderLineFulfillmentRepository(session=session),
        )

    def _override_get_production_queue_service(
        session: AsyncSession = Depends(_override_get_db_session),
        fulfillment_status_service: OrderFulfillmentStatusService = Depends(
            _override_get_fulfillment_status_service
        ),
        outbox_event_service: OutboxEventService = Depends(_override_get_outbox_service),
    ) -> ProductionQueueService:
        return ProductionQueueService(
            repository=CustomProductionJobRepository(session=session),
            fulfillment_status_service=fulfillment_status_service,
            outbox_event_service=outbox_event_service,
            packing_slip_builder=PackingSlipBuilder(settings=settings),
            artwork_client=artwork_client_stub,
            # As in production: an unprinted cancelled job refunds its line.
            refund_service=OrderRefundService(
                order_repository=OrderRepository(session=session),
                saga_repository=OrderSagaRepository(session),
                refund_repository=OrderRefundRepository(session),
                outbox_event_service=outbox_event_service,
            ),
        )

    def _override_get_order_service(
        session: AsyncSession = Depends(_override_get_db_session),
        order_item_service: OrderItemService = Depends(_override_get_order_item_service),
        order_address_service: OrderAddressService = Depends(_override_get_order_address_service),
        outbox_event_service: OutboxEventService = Depends(_override_get_outbox_service),
        fulfillment_status_service: OrderFulfillmentStatusService = Depends(
            _override_get_fulfillment_status_service
        ),
    ) -> OrderService:
        # The real OrderPricingService runs here, with only the HTTP hop to
        # product_service stubbed out. Mocking build_quote outright would skip
        # artwork-signature verification and the server-side print measurements,
        # which are exactly the guarantees the custom-T-shirt tests assert.
        pricing_service = OrderPricingService(
            settings=settings,
            catalog_client=catalog_quote_stub,
            freight_client=_StubFreightQuoteClient(),
        )
        return OrderService(
            repository=OrderRepository(session=session),
            order_item_service=order_item_service,
            order_address_service=order_address_service,
            outbox_event_service=outbox_event_service,
            pricing_service=pricing_service,
            fulfillment_status_service=fulfillment_status_service,
        )

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_order_item_service] = _override_get_order_item_service
    app.dependency_overrides[get_order_address_service] = _override_get_order_address_service
    app.dependency_overrides[get_outbox_service] = _override_get_outbox_service
    app.dependency_overrides[get_order_service] = _override_get_order_service
    app.dependency_overrides[get_fulfillment_status_service] = _override_get_fulfillment_status_service
    app.dependency_overrides[get_production_queue_service] = _override_get_production_queue_service

    SIGNING_KEYS.install_verifier(app)
    async with AsyncClient(transport=ASGITransport(app=app), auth=DEFAULT_CALLER, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode

    await test_database_session_manager.truncate_all_tables(Base.metadata)
