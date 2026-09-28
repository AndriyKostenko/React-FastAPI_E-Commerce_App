"""
Where the store sells and where its CJ goods ship from.

The store sells in Canada only, and dropshipped goods come from CJ's US
warehouses only. Both are business rules rather than tunables: the province
list and postal-code format below are Canada's, so "Canada" is not a setting
that could be flipped to another country without code changes.

order-service applies ``CanadianAddress`` before anything is priced or paid;
supplier-service applies it again before a CJ order is placed, and filters,
stocks and ships every CJ product by ``CJ_WAREHOUSE_COUNTRY_CODE``.
"""

import re
from dataclasses import dataclass

SHIPPING_COUNTRY_CODE = "CA"
SHIPPING_COUNTRY_NAME = "Canada"
CJ_WAREHOUSE_COUNTRY_CODE = "US"

# ISO 3166-2:CA codes. The names are matched case-insensitively, with the
# French names Quebec is commonly written with.
PROVINCES: dict[str, str] = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}
_PROVINCE_ALIASES: dict[str, str] = {
    **{name.lower(): code for code, name in PROVINCES.items()},
    "québec": "QC",
    "newfoundland": "NL",
    "yukon territory": "YT",
    "pei": "PE",
}
_COUNTRY_NAMES = {"canada", "ca", "can"}

# A1A 1A1. D, F, I, O, Q and U never appear, and W and Z never lead.
_POSTAL_CODE = re.compile(r"^([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z])\s?-?\s?(\d[ABCEGHJ-NPRSTV-Z]\d)$")


class NotShippableError(ValueError):
    """The address is outside the area the store ships to, or malformed for it."""


@dataclass(frozen=True)
class CanadianAddress:
    """The country, province and postal code of a shipping address, normalised."""

    country: str
    country_code: str
    province_code: str
    postal_code: str

    @classmethod
    def normalise(
        cls,
        *,
        country: str | None,
        country_code: str | None,
        province: str,
        postal_code: str,
    ) -> "CanadianAddress":
        """
        Check the address is Canadian and put it in one canonical form.

        A missing country is taken as Canada (the only one sold to), but a
        different one is refused rather than overridden. The province becomes
        its two-letter code (Stripe Tax and CJ both expect it) and the postal
        code becomes ``A1A 1A1``.
        """
        code = (country_code or "").strip().upper()
        name = (country or "").strip().lower()
        if code and code != SHIPPING_COUNTRY_CODE:
            raise NotShippableError(f"We only ship within {SHIPPING_COUNTRY_NAME} (got country code '{code}')")
        if name and name not in _COUNTRY_NAMES:
            raise NotShippableError(f"We only ship within {SHIPPING_COUNTRY_NAME} (got country '{country}')")

        province_code = cls._province_code(province)
        match = _POSTAL_CODE.match(postal_code.strip().upper())
        if match is None:
            raise NotShippableError(f"'{postal_code}' is not a Canadian postal code (expected A1A 1A1)")
        return cls(
            country=SHIPPING_COUNTRY_NAME,
            country_code=SHIPPING_COUNTRY_CODE,
            province_code=province_code,
            postal_code=f"{match.group(1)} {match.group(2)}",
        )

    @staticmethod
    def _province_code(province: str) -> str:
        cleaned = " ".join(province.strip().split())
        if cleaned.upper() in PROVINCES:
            return cleaned.upper()
        code = _PROVINCE_ALIASES.get(cleaned.lower())
        if code is None:
            raise NotShippableError(f"'{province}' is not a Canadian province or territory")
        return code
