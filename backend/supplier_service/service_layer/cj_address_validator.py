"""Shipping-address validation performed before any CJ Dropshipping call.

CJ rejects malformed addresses *after* accepting the HTTP request, which turns a
recoverable data problem into an ambiguous remote-state problem.  Validating
locally keeps every address defect on the definitive-failure path, where the
order saga can compensate and refund safely.
"""

import re
from dataclasses import dataclass
from logging import Logger

from exceptions.cj_order_exceptions import CJAddressValidationError
from shared.contracts.order import ConfirmedOrderAddress
from shared.settings import Settings


@dataclass(frozen=True, slots=True)
class ValidatedShippingAddress:
    """A shipping address that is known to satisfy CJ's field constraints."""

    name: str
    phone: str
    street: str
    city: str
    province: str
    postal_code: str
    country: str
    country_code: str

    def as_cj_fields(self) -> dict[str, str]:
        """Render the address as the shipping* keys of a createOrderV2 body."""
        return {
            "shippingCustomerName": self.name,
            "shippingPhone": self.phone,
            "shippingAddress": self.street,
            "shippingAddress2": "",
            "shippingCity": self.city,
            "shippingProvince": self.province,
            "shippingZip": self.postal_code,
            "shippingCountry": self.country,
            "shippingCountryCode": self.country_code,
        }


class CJShippingAddressValidator:
    """Normalizes and validates an order address against CJ's requirements.

    Every rule is checked before raising so the operator sees the full list of
    problems with one order instead of fixing them one redelivery at a time.
    """

    # CJ truncates silently past these lengths, which quietly misdelivers parcels.
    MAX_LENGTHS = {
        "name": 100,
        "phone": 32,
        "street": 250,
        "city": 100,
        "province": 100,
        "postal_code": 32,
        "country": 100,
    }

    # Postal formats for the destinations that make up nearly all CJ volume.
    # Anything not listed falls back to GENERIC_POSTAL_CODE.
    POSTAL_CODE_PATTERNS: dict[str, re.Pattern[str]] = {
        "US": re.compile(r"^\d{5}(-\d{4})?$"),
        "CA": re.compile(r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ ]?\d[ABCEGHJ-NPRSTV-Z]\d$", re.IGNORECASE),
        "GB": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?[ ]?\d[A-Z]{2}$", re.IGNORECASE),
        "AU": re.compile(r"^\d{4}$"),
        "NZ": re.compile(r"^\d{4}$"),
        "DE": re.compile(r"^\d{5}$"),
        "FR": re.compile(r"^\d{5}$"),
        "ES": re.compile(r"^\d{5}$"),
        "IT": re.compile(r"^\d{5}$"),
        "NL": re.compile(r"^\d{4}[ ]?[A-Z]{2}$", re.IGNORECASE),
        "PL": re.compile(r"^\d{2}-\d{3}$"),
        "JP": re.compile(r"^\d{3}-?\d{4}$"),
    }
    GENERIC_POSTAL_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{1,14}$")

    COUNTRY_CODE = re.compile(r"^[A-Za-z]{2}$")
    # A street line needs at least one digit somewhere: CJ's couriers cannot
    # deliver to a street name with no building number.
    STREET_HAS_NUMBER = re.compile(r"\d")
    PO_BOX = re.compile(r"\b(p\.?\s*o\.?\s*box|post\s+office\s+box|postbus)\b", re.IGNORECASE)
    PHONE_DIGITS = re.compile(r"\d")

    MIN_PHONE_DIGITS = 7
    MAX_PHONE_DIGITS = 15

    def __init__(self, settings: Settings, logger: Logger | None = None) -> None:
        self.settings: Settings = settings
        self.logger: Logger | None = logger

    def validate(self, address: ConfirmedOrderAddress | None) -> ValidatedShippingAddress:
        """Return a normalized address or raise with every problem found.

        Raises:
            CJAddressValidationError: If the address is missing or unusable.
        """
        if address is None:
            raise CJAddressValidationError("Shipping address is missing")

        errors: list[str] = []
        name = self._clean(address.name)
        phone = self._clean(address.phone)
        street = self._clean(address.street)
        city = self._clean(address.city)
        province = self._clean(address.province)
        postal_code = self._clean(address.postal_code)
        country = self._clean(address.country)
        country_code = self._clean(address.country_code).upper()

        for label, value in (
            ("recipient name", name),
            ("phone number", phone),
            ("street", street),
            ("city", city),
            ("province/state", province),
            ("postal code", postal_code),
            ("country code", country_code),
        ):
            if not value:
                errors.append(f"missing {label}")

        country_code = self._validate_country_code(country_code, errors)
        self._validate_lengths(
            {
                "name": name,
                "phone": phone,
                "street": street,
                "city": city,
                "province": province,
                "postal_code": postal_code,
                "country": country,
            },
            errors,
        )
        self._validate_street(street, errors)
        self._validate_postal_code(postal_code, country_code, errors)
        self._validate_phone(phone, errors)

        if errors:
            raise CJAddressValidationError(
                "Shipping address is not usable for CJ fulfillment: " + "; ".join(errors)
            )

        return ValidatedShippingAddress(
            name=name,
            phone=phone,
            street=street,
            city=city,
            province=province,
            postal_code=postal_code,
            # CJ matches on the code; the free-text name is a display fallback.
            country=country or country_code,
            country_code=country_code,
        )

    @staticmethod
    def _clean(value: str | None) -> str:
        return " ".join(value.split()) if value else ""

    def _validate_country_code(self, country_code: str, errors: list[str]) -> str:
        if not country_code:
            return country_code
        if not self.COUNTRY_CODE.match(country_code):
            errors.append(f"country code '{country_code}' is not a 2-letter ISO code")
            return country_code

        supported = {
            code.strip().upper()
            for code in self.settings.CJ_DROPSHIPPING_SUPPORTED_COUNTRY_CODES
            if code and code.strip()
        }
        if supported and country_code not in supported:
            errors.append(f"country '{country_code}' is not served by this store")
        return country_code

    def _validate_lengths(self, values: dict[str, str], errors: list[str]) -> None:
        for field, value in values.items():
            limit = self.MAX_LENGTHS[field]
            if len(value) > limit:
                errors.append(f"{field} exceeds CJ's {limit}-character limit")

    def _validate_street(self, street: str, errors: list[str]) -> None:
        if not street:
            return
        if not self.STREET_HAS_NUMBER.search(street):
            errors.append("street line has no house or building number")
        if self.settings.CJ_DROPSHIPPING_REJECT_PO_BOX_ADDRESSES and self.PO_BOX.search(street):
            errors.append("CJ couriers cannot deliver to a PO box")

    def _validate_postal_code(self, postal_code: str, country_code: str, errors: list[str]) -> None:
        if not postal_code:
            return
        pattern = self.POSTAL_CODE_PATTERNS.get(country_code, self.GENERIC_POSTAL_CODE)
        if not pattern.match(postal_code):
            errors.append(
                f"postal code '{postal_code}' is not valid for country '{country_code or 'unknown'}'"
            )

    def _validate_phone(self, phone: str, errors: list[str]) -> None:
        if not phone:
            return
        digits = self.PHONE_DIGITS.findall(phone)
        if not self.MIN_PHONE_DIGITS <= len(digits) <= self.MAX_PHONE_DIGITS:
            errors.append(
                f"phone number must contain {self.MIN_PHONE_DIGITS}-"
                f"{self.MAX_PHONE_DIGITS} digits"
            )
