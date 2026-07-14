"""HTTP client for resolving local product/variant IDs to CJ Dropshipping IDs."""
from uuid import UUID

from httpx import AsyncClient, HTTPStatusError, RequestError

from shared.schemas.product_schemas import ProductSchema
from shared.settings import Settings


class ProductServiceError(Exception):
    """Raised when the product_service cannot be reached or returns an error."""
    pass


class ProductNotFoundError(ProductServiceError):
    """Raised when a product does not exist in product_service."""
    pass


class ProductServiceClient:
    """Lightweight client that queries product_service for CJ pid/vid mapping."""

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings

    def _build_url(self, product_id: UUID) -> str:
        base = self.settings.FULL_PRODUCT_SERVICE_URL.rstrip("/")
        return f"{base}/products/{product_id}/detailed"

    async def get_product_with_variants(self, product_id: UUID) -> ProductSchema:
        """Fetch a product by ID including its variant list."""
        url = self._build_url(product_id)
        try:
            async with AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
        except RequestError as exc:
            raise ProductServiceError(f"Network error calling product_service: {exc}") from exc
        except HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ProductNotFoundError(product_id) from exc
            raise ProductServiceError(
                f"product_service returned {exc.response.status_code}: {exc.response.text}"
            ) from exc

        try:
            return ProductSchema(**response.json())
        except Exception as exc:
            raise ProductServiceError(f"Invalid product_service response: {exc}") from exc

    async def resolve_cj_ids(
        self,
        product_id: UUID,
        variant_id: UUID | None = None,
    ) -> tuple[str, str]:
        """Resolve a local product/variant pair to CJ pid/vid.

        Args:
            product_id: Local product UUID.
            variant_id: Local variant UUID. If omitted, the product's first variant is used.

        Returns:
            Tuple of (CJ pid, CJ vid).

        Raises:
            ProductNotFoundError: If the product or variant cannot be found.
            ProductServiceError: If the product has no CJ pid or no variants.
        """
        product = await self.get_product_with_variants(product_id)
        if not product.pid:
            raise ProductServiceError(f"Product {product_id} has no CJ pid")

        variants = product.variants or []
        if not variants:
            raise ProductServiceError(f"Product {product_id} has no variants")

        if variant_id is None:
            variant = variants[0]
        else:
            variant = next((v for v in variants if v.id == variant_id), None)
            if variant is None:
                raise ProductNotFoundError(variant_id)

        return product.pid, variant.vid
