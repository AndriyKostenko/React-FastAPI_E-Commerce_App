from collections.abc import Iterable

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.catalogue_image_mirror_models import CatalogueImageMirror, MirrorStatus
from models.product_image_models import ProductImage
from models.product_models import Product
from models.product_variant_models import ProductVariant
from shared.database_layer.database_layer import BaseRepository


class CatalogueImageMirrorRepository(BaseRepository[CatalogueImageMirror]):
    """Supplier images copied into the catalogue store, and the rows using them."""

    # Every catalogue column that may hold a supplier URL. Distinct values
    # only: one image is often both a product's main image and a gallery or
    # variant image.
    _EXTERNAL_URLS_IN_USE = text(
        """
        SELECT u.url
        FROM (
            SELECT image_url AS url FROM product_images
            UNION SELECT image_url FROM products WHERE image_url IS NOT NULL
            UNION SELECT variant_image FROM product_variants WHERE variant_image IS NOT NULL
        ) AS u
        LEFT JOIN catalogue_image_mirrors AS m ON m.source_url = u.url
        WHERE (u.url LIKE 'https://%' OR u.url LIKE 'http://%')
          AND (m.status IS NULL OR m.status <> :failed)
        ORDER BY u.url
        """
    )

    def __init__(self, session: AsyncSession):
        super().__init__(session, CatalogueImageMirror)

    async def external_urls_in_use(self) -> list[str]:
        """Supplier URLs still referenced by a product, except those given up on."""
        result = await self.session.execute(self._EXTERNAL_URLS_IN_USE, {"failed": MirrorStatus.FAILED.value})
        return list(result.scalars().all())

    async def get_by_source_urls(self, urls: Iterable[str]) -> dict[str, CatalogueImageMirror]:
        wanted = list(dict.fromkeys(urls))
        if not wanted:
            return {}
        result = await self.session.execute(
            select(CatalogueImageMirror).where(CatalogueImageMirror.source_url.in_(wanted))
        )
        return {row.source_url: row for row in result.scalars().all()}

    async def get_for_update(self, source_url: str) -> CatalogueImageMirror | None:
        result = await self.session.execute(
            select(CatalogueImageMirror)
            .where(CatalogueImageMirror.source_url == source_url)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def mirrored_keys(self, urls: Iterable[str]) -> dict[str, str]:
        """source URL -> object key, for the URLs that have been copied."""
        wanted = [url for url in dict.fromkeys(urls) if url]
        if not wanted:
            return {}
        result = await self.session.execute(
            select(CatalogueImageMirror.source_url, CatalogueImageMirror.object_key).where(
                CatalogueImageMirror.source_url.in_(wanted),
                CatalogueImageMirror.status == MirrorStatus.MIRRORED.value,
            )
        )
        return {source_url: key for source_url, key in result.all() if key}

    async def rewrite_references(self, source_url: str, object_key: str) -> int:
        """Point every row still using ``source_url`` at the copied object."""
        statements = (
            update(ProductImage).where(ProductImage.image_url == source_url).values(image_url=object_key),
            update(Product).where(Product.image_url == source_url).values(image_url=object_key),
            update(ProductVariant).where(ProductVariant.variant_image == source_url).values(variant_image=object_key),
        )
        rewritten = 0
        for statement in statements:
            result = await self.session.execute(statement.execution_options(synchronize_session=False))
            rewritten += result.rowcount or 0
        return rewritten
