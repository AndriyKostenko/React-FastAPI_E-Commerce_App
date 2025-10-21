from pydantic import BaseModel


def parse_filter_params(query_filters: BaseModel) -> dict:
    """
    Parses the FilterParams object into a dictionary suitable for querying the database.

    Args:
        filter_query (FilterParams): The filter parameters provided by the user.

    Returns:
        dict: A dictionary representation of the filter parameters.
    """
    params = query_filters.model_dump(exclude_none=True)
    # Convert camelCase to snake_case
    return {
        ''.join(['_' + char.lower() if char.isupper() else char for char in key]).lstrip('_'): value
        for key, value in params.items()
    }
