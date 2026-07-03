import re
from typing import Any
from decimal import Decimal, ROUND_HALF_UP

from exceptions.product_exceptions import CJDropshippingAPIError
from shared.schemas.product_schemas import CreateProduct


class CJRoductSchemaMapper:
	"""
	Extracts the minimum price from a string that may contain a range.

	Handles:
	- "7.13 -- 7.77" -> 7.13
	- "0.68"         -> 0.68
	- "$7.13 - 7.77" -> 7.13
	"""
	# Pre-compiled regex for speed
	RANGE_SPLIT_REGEX = re.compile(r'\s*--\s*|\s*-\s*')
	CLEAN_REGEX = re.compile(r'[^\d.]')

	@staticmethod
	def _parse_price(price_str: str | None) -> Decimal:
		if not price_str:
			return Decimal("0.00")
		parts = CJRoductSchemaMapper.RANGE_SPLIT_REGEX.split(price_str)
		clean_price = CJRoductSchemaMapper.CLEAN_REGEX.sub('', parts[0])
		try:
			price = Decimal(clean_price)
			return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
		except (Exception, ValueError):
			return Decimal('0.00')


	@classmethod
	def map_products(cls, data: Any):
		content_list = data.get("data", {}).get("content", [])
		if not content_list:
			raise CJDropshippingAPIError("No products found in CJDropshipping /products response.")
		raw_products = content_list[0].get("productList", [])
		if not raw_products:
			raise CJDropshippingAPIError("No products found in CJDropshipping contentList.")
		mapped_products: list[CreateProduct] = []
		for product in raw_products:
			stock_qty = product.get("warehouseInventoryNum") or 0
			mapped_products.append(
                CreateProduct(
                	id=product.get("id"),
                    name=product.get("nameEn", ""),
                    sku=product.get("sku", ""),
                    image_url=product.get("bigImage", ""),
                    price=cls._parse_price(product.get("sellPrice", "0")),
                    description="",
                    category_id=product.get("categoryId"),
                    brand="",
                    quantity=stock_qty,
                    in_stock=stock_qty > 0,
                )
            )

		return mapped_products
