from typing import Any, Optional

from pydantic import BaseModel


class FilterParser:
    """Utility class for parsing the filter parameters into repository compatible forms"""

    @staticmethod
    def parse_filter_params(
        filter_query: BaseModel, search_fields: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Parse filter parameters from Pydantic model into repository-compatible parameters.

        Args:
            filters_query: Pydantic model with filter parameters
            search_fields: List of fields to search in (optional)

        Returns:
            Dictionary with:
            - filters: dict of field filters
            - sort_by: sorting field
            - sort_order: asc/desc
            - offset: pagination offset
            - limit: pagination limit
            - search_term: search string
            - date_filters: dict of date range filters
            - range_filters: dict of numeric range filters
            - search_fields: list of searchable fields
        """
        filters_dict = filter_query.model_dump()
        date_filters = {
            "date_created_from": filters_dict.get("date_created_from"),
            "date_created_to": filters_dict.get("date_created_to"),
            "date_updated_from": filters_dict.get("date_updated_from"),
            "date_updated_to": filters_dict.get("date_updated_to"),
        }
        range_filters = FilterParser.extract_range_filters(filters_dict)

        return {
            "filters": {
                key: value for key, value in filters_dict.items() if value is not None
            },
            "sort_by": filters_dict.get("sort_by"),
            "sort_order": filters_dict.get("sort_order"),
            "offset": filters_dict.get("offset"),
            "limit": filters_dict.get("limit"),
            "search_term": filters_dict.get("search_term"),
            "date_filters": {
                key: value for key, value in date_filters.items() if value is not None
            },
            "search_fields": search_fields or [],
            "range_filters": range_filters,
        }

    @staticmethod
    def extract_range_filters(filters_dict: dict[str, Any]):
        """
        Extract range filters (min/max pairs) from filters dictionary.

        Automatically detects pairs like:
        - min_price/max_price -> price: (min, max)
        - min_quantity/max_quantity -> quantity: (min, max)
        - min_rating/max_rating -> rating: (min, max)
        """
        range_filters = {}
        keys = list(filters_dict.keys())

        for key in keys:
            if key.startswith("min_"):
                field = key[4:]  # Removing prefix min_
                min_value = filters_dict.get(f"min_{field}")
                max_value = filters_dict.get(f"max_{field}")
                if min_value or max_value:
                    range_filters[field] = (min_value, max_value)

            elif key.startswith("max_"):
                field = key[4:]
                if field not in range_filters:
                    min_value = filters_dict.get(f"min_{field}")
                    max_value = filters_dict.get(f"max_{field}")
                    if min_value or max_value:
                        range_filters[field] = (min_value, max_value)
