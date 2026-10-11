"""
Where the store sells and where its CJ goods ship from.

The store sells in Canada only, and dropshipped goods come from CJ's China
warehouses only. CJ has no carrier from its US warehouses to Canada (checked
2026-10-02: zero freight options US->CA for every T-shirt, 16 from CN), and
its Canadian warehouse stocks almost none of the range. Both are business
rules rather than tunables: the province
list and postal-code format below are Canada's, so "Canada" is not a setting
that could be flipped to another country without code changes.

order-service applies ``CanadianAddress`` before anything is priced or paid;
supplier-service applies it again before a CJ order is placed, and filters,
stocks and ships every CJ product by ``CJ_WAREHOUSE_COUNTRY_CODE``.
"""


SHIPPING_COUNTRY_CODE = "CA"


SHIPPING_COUNTRY_NAME = "Canada"


CJ_WAREHOUSE_COUNTRY_CODE = "CN"
