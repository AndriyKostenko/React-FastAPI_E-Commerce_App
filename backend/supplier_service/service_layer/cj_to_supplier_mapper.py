import json
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.schemas.supplier_schemas import GenericSupplierProduct, SupplierProductVariant, SupplierProductsPage
from shared.integrations.cj_api_client import CJDropshippingAPIError


class CJToSupplierMapper:
    """Maps CJDropshipping API responses into generic supplier product schemas."""

    SUPPLIER_ID = "cjdropshipping"
    RANGE_SPLIT_REGEX = re.compile(r"\s*--\s*|\s+-\s+")
    CLEAN_REGEX = re.compile(r"[^\d.]")

    @staticmethod
    def _parse_price(price_str: str | None) -> Decimal:
        if not price_str:
            return Decimal("0.00")
        parts = CJToSupplierMapper.RANGE_SPLIT_REGEX.split(str(price_str))
        clean_price = CJToSupplierMapper.CLEAN_REGEX.sub("", parts[0])
        try:
            price = Decimal(clean_price)
            return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (Exception, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_json_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @classmethod
    def map_products_page(cls, data: Any, page: int = 1, page_size: int = 10) -> SupplierProductsPage:
        """Map a CJ /product/listV2 response to a SupplierProductsPage."""
        content_list = data.get("data", {}).get("content", [])
        if not content_list:
            raise CJDropshippingAPIError("No products found in CJDropshipping /products response.")

        pagination = content_list[0].get("page", {}) if content_list else {}
        raw_products = content_list[0].get("productList", []) if content_list else []

        mapped_products: list[GenericSupplierProduct] = []
        for product in raw_products:
            stock_qty = product.get("warehouseInventoryNum") or 0
            mapped_products.append(
                GenericSupplierProduct(
                    supplier_id=cls.SUPPLIER_ID,
                    supplier_pid=product.get("id"),
                    name=product.get("nameEn", ""),
                    sku=product.get("sku", ""),
                    image_url=product.get("bigImage", ""),
                    price=cls._parse_price(product.get("sellPrice", "0")),
                    description="",
                    category_id=product.get("categoryId"),
                    category_name=None,
                    brand="cjdropshipping",
                    quantity=stock_qty,
                    in_stock=stock_qty > 0,
                    variants=[],
                    images=[],
                )
            )

        return SupplierProductsPage(
            page=page,
            page_size=page_size,
            total_records=pagination.get("totalRecords"),
            total_pages=pagination.get("totalPages"),
            products=mapped_products,
        )

    @classmethod
    def map_product_details(cls, data: Any) -> GenericSupplierProduct:
        """Map a CJ /product/query response to a fully populated GenericSupplierProduct."""
        raw = data.get("data") if isinstance(data, dict) else None
        if not raw:
            raise CJDropshippingAPIError("No product data found in CJDropshipping detail response.")

        pid = raw.get("pid")
        if not pid:
            raise CJDropshippingAPIError("CJ product detail missing pid.")

        stock_qty = raw.get("warehouseInventoryNum") or raw.get("totalVerifiedInventory") or 0
        variants = [cls._map_variant(v) for v in raw.get("variants", []) if isinstance(v, dict)]
        images = cls._parse_json_list(raw.get("productImageSet"))

        return GenericSupplierProduct(
            supplier_id=cls.SUPPLIER_ID,
            supplier_pid=pid,
            name=raw.get("productNameEn", ""),
            sku=raw.get("productSku", ""),
            image_url=raw.get("bigImage", ""),
            price=cls._parse_price(raw.get("sellPrice", "0")),
            description=raw.get("description", ""),
            category_id=raw.get("categoryId"),
            category_name=None,
            brand="cjdropshipping",
            quantity=stock_qty,
            in_stock=stock_qty > 0,
            variants=variants,
            images=images,
        )

    @classmethod
    def _map_variant(cls, raw_variant: dict[str, Any]) -> SupplierProductVariant:
        return SupplierProductVariant(
            vid=raw_variant.get("vid", ""),
            variant_key=raw_variant.get("variantKey"),
            variant_name_en=raw_variant.get("variantNameEn"),
            variant_sku=raw_variant.get("variantSku"),
            barcode=raw_variant.get("barcode"),
            variant_image=raw_variant.get("variantImage"),
            variant_weight=Decimal(str(raw_variant["variantWeight"])) if raw_variant.get("variantWeight") is not None else None,
            variant_length=cls._parse_int(raw_variant.get("variantLength")),
            variant_width=cls._parse_int(raw_variant.get("variantWidth")),
            variant_height=cls._parse_int(raw_variant.get("variantHeight")),
            variant_sell_price=Decimal(str(raw_variant["variantSellPrice"])) if raw_variant.get("variantSellPrice") is not None else None,
            variant_sug_sell_price=Decimal(str(raw_variant["variantSugSellPrice"])) if raw_variant.get("variantSugSellPrice") is not None else None,
            inventory_num=cls._parse_int(raw_variant.get("inventoryNum")),
        )
