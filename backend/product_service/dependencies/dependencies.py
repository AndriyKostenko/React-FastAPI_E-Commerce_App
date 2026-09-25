from typing import Annotated
from collections.abc import AsyncGenerator

from aiohttp import ClientSession
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.category_repository import CategoryRepository
from database_layer.product_image_repository import ProductImageRepository
from database_layer.product_repository import ProductRepository
from database_layer.product_variant_repository import ProductVariantRepository
from database_layer.retained_artwork_repository import RetainedArtworkRepository
from database_layer.review_repository import ReviewRepository
from shared.utils.authenticated_caller import AuthenticatedCaller
from service_layer.background_removal_service import RembgBackgroundRemover
from service_layer.artwork_asset_service import ArtworkAssetService
from service_layer.category_service import CategoryService
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_generation_service import ImageGenerationService
from service_layer.image_job_store import ImageJobStore
from service_layer.image_storage_service import ImageStorageService
from service_layer.openrouter_client import OpenRouterClient
from service_layer.product_image_service import ProductImageService
from service_layer.product_service import ProductService
from service_layer.review_service import ReviewService
from resources import ProductApiResources, get_product_api_resources


def get_resources(request: Request) -> ProductApiResources:
    """Return resources owned by this FastAPI application instance."""
    return get_product_api_resources(request)


# Always depended on with scope="function": FastAPI's default runs a yield
# dependency's exit code after the response is sent, so the commit below ran
# after the client had been told "created" — a commit that then failed lost the
# write silently. Function scope commits before the response goes out.
async def get_db_session(
    resources: ProductApiResources = Depends(get_resources),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()
    """
    async with resources.database.transaction() as session:
        yield session


def get_category_service(
    resources: ProductApiResources = Depends(get_resources),
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> CategoryService:
    """Dependency to provide CategoryService."""
    return CategoryService(
        CategoryRepository(session=session),
        default_category_name=resources.settings.CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME,
    )


def get_review_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> ReviewService:
    """Dependency to provide ReviewService."""
    return ReviewService(ReviewRepository(session=session))


def get_product_image_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> ProductImageService:
    """Dependency to provide ProductImageService."""
    return ProductImageService(ProductImageRepository(session=session))


def get_product_service(
    resources: ProductApiResources = Depends(get_resources),
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> ProductService:
    """Dependency to provide ProductService."""
    image_repo = ProductImageRepository(session=session)
    product_image_service = ProductImageService(repository=image_repo)
    product_repo = ProductRepository(session=session)
    category_service = CategoryService(
        CategoryRepository(session=session),
        default_category_name=resources.settings.CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME,
    )
    return ProductService(
        repository=product_repo,
        product_image_service=product_image_service,
        variant_repository=ProductVariantRepository(session=session),
        image_repository=image_repo,
        category_service=category_service,
    )

# ── image-generation dependency chain ─────────────────────────────────────────

def get_http_session(resources: ProductApiResources = Depends(get_resources)) -> ClientSession:
    """Return the shared aiohttp ClientSession stored on app.state during lifespan."""
    return resources.http_session


def get_openrouter_client(
    resources: ProductApiResources = Depends(get_resources),
    session: ClientSession = Depends(get_http_session),
) -> OpenRouterClient:
    return OpenRouterClient(
        session=session,
        settings=resources.settings,
        logger=resources.logger,
    )


def get_generation_quota_service(
    resources: ProductApiResources = Depends(get_resources),
) -> GenerationQuotaService:
    return GenerationQuotaService(
        cache_manager=resources.cache,
        settings=resources.settings,
        logger=resources.logger,
    )


def get_image_job_store(
    resources: ProductApiResources = Depends(get_resources),
) -> ImageJobStore:
    return ImageJobStore(
        cache_manager=resources.cache,
        logger=resources.logger,
    )


def get_image_storage_service(
    resources: ProductApiResources = Depends(get_resources),
) -> ImageStorageService:
    return ImageStorageService(logger=resources.logger, settings=resources.settings)


def get_image_generation_service(
    resources: ProductApiResources = Depends(get_resources),
    openrouter_client: OpenRouterClient = Depends(get_openrouter_client),
    quota_service: GenerationQuotaService = Depends(get_generation_quota_service),
    job_store: ImageJobStore = Depends(get_image_job_store),
    storage_service: ImageStorageService = Depends(get_image_storage_service),
) -> ImageGenerationService:
    return ImageGenerationService(
        openrouter_client=openrouter_client,
        quota_service=quota_service,
        job_store=job_store,
        storage_service=storage_service,
        background_remover=RembgBackgroundRemover(settings=resources.settings, logger=resources.logger),
        settings=resources.settings,
        logger=resources.logger,
    )


def get_artwork_asset_service(
    resources: ProductApiResources = Depends(get_resources),
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> ArtworkAssetService:
    """Dependency to provide ArtworkAssetService for print-file downloads and retention."""
    return ArtworkAssetService(
        logger=resources.logger,
        settings=resources.settings,
        repository=RetainedArtworkRepository(session=session),
    )


def get_authenticated_caller(request: Request) -> AuthenticatedCaller:
    """The signed-in user the API gateway asserted, or 401."""
    return AuthenticatedCaller.require(request)


def get_admin_caller(
    request: Request,
    resources: ProductApiResources = Depends(get_resources),
) -> AuthenticatedCaller:
    """The asserted caller if they are an admin; 401/403 otherwise."""
    return AuthenticatedCaller.require_admin(request, resources.settings.SECRET_ROLE)


product_service_dependency = Annotated[ProductService, Depends(get_product_service)]
category_service_dependency = Annotated[CategoryService, Depends(get_category_service)]
review_service_dependency = Annotated[ReviewService, Depends(get_review_service)]
product_image_service_dependency = Annotated[ProductImageService, Depends(get_product_image_service)]
image_generation_service_dependency = Annotated[ImageGenerationService, Depends(get_image_generation_service)]
authenticated_caller_dependency = Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)]
admin_caller_dependency = Annotated[AuthenticatedCaller, Depends(get_admin_caller)]
artwork_asset_service_dependency = Annotated[ArtworkAssetService, Depends(get_artwork_asset_service)]
