from html import unescape
import re
from uuid import UUID

from schemas.product_schemas import CreateProduct, CreateProductVariant
from shared.contracts.supplier import GenericSupplierProduct, SupplierProductVariant


class SupplierProductMapper:
    """Maps generic supplier product schemas to product_service CreateProduct schemas."""

    DESCRIPTION_MAX_LENGTH = 2000
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

    @classmethod
    def map_supplier_product(
        cls,
        supplier_product: GenericSupplierProduct,
        local_category_id: UUID,
    ) -> CreateProduct:
        """Convert a GenericSupplierProduct to a CreateProduct."""
        return CreateProduct(
            id=None,
            pid=supplier_product.supplier_pid,
            supplier_id=supplier_product.supplier_id,
            supplier_category_id=supplier_product.supplier_category_id,
            name=supplier_product.name,
            description=cls._normalize_description(supplier_product.description),
            category_id=local_category_id,
            brand=supplier_product.brand,
            quantity=supplier_product.quantity,
            price=supplier_product.price,
            in_stock=supplier_product.in_stock,
            sku=supplier_product.sku,
            image_url=supplier_product.image_url,
            variants=[cls._map_variant(v) for v in (supplier_product.variants or [])],
            images=supplier_product.images or [],
        )

    @classmethod
    def map_supplier_products(
        cls,
        supplier_products: list[GenericSupplierProduct],
        local_category_id: UUID,
    ) -> list[CreateProduct]:
        """Convert a list of GenericSupplierProduct to a list of CreateProduct."""
        return [cls.map_supplier_product(product, local_category_id) for product in supplier_products]

    @classmethod
    def _map_variant(cls, variant: SupplierProductVariant) -> CreateProductVariant:
        return CreateProductVariant(
            vid=variant.vid,
            variant_key=variant.variant_key,
            variant_name_en=variant.variant_name_en,
            variant_sku=variant.variant_sku,
            barcode=variant.barcode,
            variant_image=variant.variant_image,
            variant_weight=variant.variant_weight,
            variant_length=variant.variant_length,
            variant_width=variant.variant_width,
            variant_height=variant.variant_height,
            variant_sell_price=variant.variant_sell_price,
            variant_sug_sell_price=variant.variant_sug_sell_price,
            inventory_num=variant.inventory_num,
        )

    @classmethod
    def _normalize_description(cls, description: str | None) -> str:
        """Convert supplier HTML to bounded plain text accepted by CreateProduct."""
        without_tags = cls.HTML_TAG_PATTERN.sub(" ", description or "")
        normalized = " ".join(unescape(without_tags).split())
        return normalized[: cls.DESCRIPTION_MAX_LENGTH]
