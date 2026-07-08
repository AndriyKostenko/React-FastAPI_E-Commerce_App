from typing import Any

from shared.schemas.dropshipping_schemas import CJProductsFilterParams


class CJFilterParser:
    """Parse CJ Dropshipping filter parameters into API-compatible query params."""

    @staticmethod
    def parse_filter_params(filter_query: CJProductsFilterParams) -> dict[str, Any]:
        """Convert a CJProductsFilterParams model into a flat dict for query strings.

        Only fields that are not None are included, so CJ receives a clean URL.
        """
        return filter_query.model_dump(exclude_none=True)
