"""
Shared pytest fixtures for product_service unit and integration tests.

All unit-test fixtures replace heavy external dependencies (DB, RabbitMQ)
with mocks so the tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(PRODUCT_SERVICE_TEST_DB) and truncate every table between tests.
"""
import os
import tempfile

# Ensure the media mount point exists before importing main.py,
# which calls app.mount("/media", StaticFiles(directory="/media"), ...).
# In Docker the real /media dir is used; locally we fall back to a temp dir.
_MEDIA_ROOT = "/media"
try:
    os.makedirs(os.path.join(_MEDIA_ROOT, "images"), exist_ok=True)
    os.makedirs(os.path.join(_MEDIA_ROOT, "icons"), exist_ok=True)
except OSError:
    _tmp_media = tempfile.mkdtemp(prefix="product_service_media_")
    _MEDIA_ROOT = _tmp_media
    os.makedirs(os.path.join(_MEDIA_ROOT, "images"), exist_ok=True)
    os.makedirs(os.path.join(_MEDIA_ROOT, "icons"), exist_ok=True)
    os.environ.setdefault("MEDIA_ROOT", _MEDIA_ROOT)

from collections.abc import AsyncGenerator
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
from database_layer.category_repository import CategoryRepository
from database_layer.product_repository import ProductRepository
from database_layer.review_repository import ReviewRepository
from database_layer.product_image_repository import ProductImageRepository
from dependencies.dependencies import (
    get_db_session,
    get_category_service,
    get_product_service,
    get_review_service,
    get_product_image_service,
    get_image_generation_service,
)
from service_layer.category_service import CategoryService
from service_layer.product_service import ProductService
from service_layer.review_service import ReviewService
from service_layer.product_image_service import ProductImageService
from service_layer.image_generation_service import ImageGenerationService
from shared.shared_instances import test_product_service_database_session_manager, test_settings
from shared.schemas.product_schemas import ProductBase, ProductSchema
from shared.schemas.category_schema import CategorySchema
from shared.schemas.review_schemas import ReviewSchema
from shared.schemas.product_image_schema import ImageType
from shared.schemas.image_generation_schema import GenerateImageResponse


# ---------------------------------------------------------------------------
# Shared test-data constants — sourced from shared TestSettings
# ---------------------------------------------------------------------------

TEST_PRODUCT_ID  = test_settings.TEST_PRODUCT_ID
TEST_CATEGORY_ID = test_settings.TEST_CATEGORY_ID
TEST_REVIEW_ID   = test_settings.TEST_REVIEW_ID
TEST_USER_ID     = test_settings.TEST_USER_ID
TEST_DATETIME    = test_settings.TEST_DATETIME
TEST_API         = test_settings.API

MOCK_CATEGORY_SCHEMA = test_settings.MOCK_CATEGORY_SCHEMA
MOCK_PRODUCT_BASE    = test_settings.MOCK_PRODUCT_BASE
MOCK_PRODUCT_SCHEMA  = test_settings.MOCK_PRODUCT_SCHEMA
MOCK_REVIEW_SCHEMA   = test_settings.MOCK_REVIEW_SCHEMA


# ---------------------------------------------------------------------------
# ORM mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_product_orm() -> MagicMock:
    """Fake SQLAlchemy Product ORM object with all required attributes."""
    product = MagicMock()
    product.id = TEST_PRODUCT_ID
    product.name = "test laptop"
    product.description = "A high-quality test laptop for testing purposes"
    product.category_id = TEST_CATEGORY_ID
    product.brand = "testbrand"
    product.quantity = 10
    product.price = Decimal("999.99")
    product.in_stock = True
    product.date_created = TEST_DATETIME
    product.date_updated = None
    product.reviews = []
    product.images = []
    product.category = None
    return product


@pytest.fixture
def mock_category_orm() -> MagicMock:
    """Fake SQLAlchemy ProductCategory ORM object."""
    category = MagicMock()
    category.id = TEST_CATEGORY_ID
    category.name = "electronics"
    category.image_url = None
    category.date_created = TEST_DATETIME
    category.date_updated = None
    category.products = []
    return category


@pytest.fixture
def mock_review_orm() -> MagicMock:
    """Fake SQLAlchemy ProductReview ORM object."""
    review = MagicMock()
    review.id = TEST_REVIEW_ID
    review.product_id = TEST_PRODUCT_ID
    review.user_id = TEST_USER_ID
    review.comment = "Great product!"
    review.rating = 4.5
    review.date_created = TEST_DATETIME
    review.date_updated = None
    return review


# ---------------------------------------------------------------------------
# Repository mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_product_repository() -> MagicMock:
    """Mock ProductRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_field = AsyncMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.delete_by_id = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.atomic_decrement_quantity = AsyncMock()
    repo.atomic_increment_quantity = AsyncMock()
    return repo


@pytest.fixture
def mock_category_repository() -> MagicMock:
    """Mock CategoryRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_field = AsyncMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.delete_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_review_repository() -> MagicMock:
    """Mock ReviewRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_field = AsyncMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.delete_by_id = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.filter_by = AsyncMock()
    return repo


@pytest.fixture
def mock_product_image_service() -> MagicMock:
    """Mock ProductImageService for use when testing ProductService."""
    svc = MagicMock()
    svc.create_product_images = AsyncMock(return_value=[])
    svc.get_product_images = AsyncMock(return_value=[])
    svc.delete_all_product_images = AsyncMock(return_value=0)
    return svc


# ---------------------------------------------------------------------------
# Service fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def product_service_unit(
    mock_product_repository: MagicMock,
    mock_product_image_service: MagicMock,
) -> ProductService:
    """ProductService wired with all mocked dependencies."""
    return ProductService(
        repository=mock_product_repository,
        product_image_service=mock_product_image_service,
    )


@pytest.fixture
def category_service_unit(mock_category_repository: MagicMock) -> CategoryService:
    """CategoryService wired with a mocked repository."""
    return CategoryService(repository=mock_category_repository)


@pytest.fixture
def review_service_unit(mock_review_repository: MagicMock) -> ReviewService:
    """ReviewService wired with a mocked repository."""
    return ReviewService(repository=mock_review_repository)


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_route_product_service() -> MagicMock:
    """Full mock of ProductService for app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_product_item = AsyncMock(return_value=MOCK_PRODUCT_BASE)
    svc.create_product_with_images = AsyncMock(return_value=MOCK_PRODUCT_SCHEMA)
    svc.get_all_products_without_relations = AsyncMock(return_value=[MOCK_PRODUCT_BASE])
    svc.get_all_products_with_relations = AsyncMock(return_value=[MOCK_PRODUCT_SCHEMA])
    svc.get_product_by_id_without_relations = AsyncMock(return_value=MOCK_PRODUCT_BASE)
    svc.get_product_by_id_with_relations = AsyncMock(return_value=MOCK_PRODUCT_SCHEMA)
    svc.get_product_by_name = AsyncMock(return_value=MOCK_PRODUCT_BASE)
    svc.update_product = AsyncMock(return_value=MOCK_PRODUCT_BASE)
    svc.delete_product_by_id = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_route_category_service() -> MagicMock:
    """Full mock of CategoryService for app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_category = AsyncMock(return_value=MOCK_CATEGORY_SCHEMA)
    svc.get_all_categories = AsyncMock(return_value=[MOCK_CATEGORY_SCHEMA])
    svc.get_category_by_id = AsyncMock(return_value=MOCK_CATEGORY_SCHEMA)
    svc.get_category_by_name = AsyncMock(return_value=MOCK_CATEGORY_SCHEMA)
    svc.update_category = AsyncMock(return_value=MOCK_CATEGORY_SCHEMA)
    svc.delete_category = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_route_review_service() -> MagicMock:
    """Full mock of ReviewService for app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_product_review = AsyncMock(return_value=MOCK_REVIEW_SCHEMA)
    svc.get_all_reviews = AsyncMock(return_value=[MOCK_REVIEW_SCHEMA])
    svc.get_review_by_id = AsyncMock(return_value=MOCK_REVIEW_SCHEMA)
    svc.get_reviews_by_product_id = AsyncMock(return_value=[MOCK_REVIEW_SCHEMA])
    svc.get_reviews_by_user_id = AsyncMock(return_value=[MOCK_REVIEW_SCHEMA])
    svc.get_review_by_product_id_and_user_id = AsyncMock(return_value=MOCK_REVIEW_SCHEMA)
    svc.update_product_review = AsyncMock(return_value=MOCK_REVIEW_SCHEMA)
    svc.delete_product_review = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_route_image_generation_service() -> MagicMock:
    svc = MagicMock(spec=ImageGenerationService)
    svc.GUEST_QUOTA_COOKIE = "guest_generation_id"
    svc.settings = MagicMock()
    svc.settings.SECURE_COOKIES = False
    svc.settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS = 24
    svc.generate_image = AsyncMock(
        return_value=GenerateImageResponse(
            image_url="/media/generated/fake-image.png",
            model="openai/gpt-image-1",
            remaining_generations=2,
            guest_limit=3,
        )
    )
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan replaces the real one to avoid DB/Redis/RabbitMQ connections."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_product_service: MagicMock,
    mock_route_category_service: MagicMock,
    mock_route_review_service: MagicMock,
    mock_route_image_generation_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.

    - Replaces the FastAPI lifespan with a no-op so startup/shutdown don't
      attempt live connections.
    - Overrides all service dependencies so no real DB is needed.
    """
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_product_service] = lambda: mock_route_product_service
    app.dependency_overrides[get_category_service] = lambda: mock_route_category_service
    app.dependency_overrides[get_review_service] = lambda: mock_route_review_service
    app.dependency_overrides[get_image_generation_service] = lambda: mock_route_image_generation_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Integration-test fixtures  (real DB + real services)
# ---------------------------------------------------------------------------

@pytest.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (product_service TEST database)
      - ProductService, CategoryService, ReviewService, ProductImageService
      - All repositories

    What is mocked:
      - FastAPI lifespan (tables are managed by this fixture directly)

    Isolation strategy:
      - Before yield : create all tables (idempotent) so the schema is fresh.
      - After  yield : TRUNCATE every table so the next test starts clean.
    """
    # ── 1. Ensure the test schema exists ────────────────────────────────────
    await test_product_service_database_session_manager.init_db()

    # ── 2. Dependency overrides — wire real services to test DB session ──────
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_product_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_category_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> CategoryService:
        return CategoryService(CategoryRepository(session=session))

    def _override_get_product_image_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> ProductImageService:
        return ProductImageService(ProductImageRepository(session=session))

    def _override_get_review_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> ReviewService:
        return ReviewService(ReviewRepository(session=session))

    def _override_get_product_service(
        session: AsyncSession = Depends(_override_get_db_session),
        product_image_service: ProductImageService = Depends(_override_get_product_image_service),
    ) -> ProductService:
        return ProductService(ProductRepository(session=session), product_image_service)

    # ── 3. Replace the app lifespan so no live infra connections are made ───
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_category_service] = _override_get_category_service
    app.dependency_overrides[get_product_image_service] = _override_get_product_image_service
    app.dependency_overrides[get_review_service] = _override_get_review_service
    app.dependency_overrides[get_product_service] = _override_get_product_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan

    # ── 4. Wipe all rows so the next test starts with an empty database ─────
    await test_product_service_database_session_manager.truncate_all_tables()
