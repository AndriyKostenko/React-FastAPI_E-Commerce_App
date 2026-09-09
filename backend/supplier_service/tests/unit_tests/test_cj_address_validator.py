"""Unit tests for CJShippingAddressValidator."""
import pytest

from exceptions.cj_order_exceptions import CJAddressValidationError
from service_layer.cj_address_validator import CJShippingAddressValidator
from shared.contracts.order import ConfirmedOrderAddress
from shared.settings import get_settings


def _address(**overrides) -> ConfirmedOrderAddress:
    fields = {
        "street": "123 Test Street",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5V 2T6",
        "country": "Canada",
        "country_code": "ca",
        "name": "Test User",
        "phone": "+1 (416) 555-0123",
    }
    fields.update(overrides)
    return ConfirmedOrderAddress(**fields)


@pytest.fixture
def validator() -> CJShippingAddressValidator:
    settings = get_settings().model_copy()
    settings.CJ_DROPSHIPPING_SUPPORTED_COUNTRY_CODES = []
    settings.CJ_DROPSHIPPING_REJECT_PO_BOX_ADDRESSES = True
    return CJShippingAddressValidator(settings)


class TestValidAddresses:
    def test_normalizes_country_code_and_whitespace(self, validator) -> None:
        validated = validator.validate(
            _address(street="  123   Test   Street ", country_code="ca")
        )

        assert validated.country_code == "CA"
        assert validated.street == "123 Test Street"

    def test_renders_cj_shipping_fields(self, validator) -> None:
        fields = validator.validate(_address()).as_cj_fields()

        assert fields["shippingCountryCode"] == "CA"
        assert fields["shippingZip"] == "M5V 2T6"
        assert fields["shippingCustomerName"] == "Test User"
        assert fields["shippingAddress2"] == ""

    def test_falls_back_to_country_code_when_country_name_missing(self, validator) -> None:
        validated = validator.validate(_address(country=None))

        assert validated.country == "CA"

    @pytest.mark.parametrize(
        ("country_code", "postal_code"),
        [
            ("US", "10001"),
            ("US", "10001-1234"),
            ("GB", "SW1A 1AA"),
            ("DE", "10115"),
            ("NL", "1012 AB"),
            ("JP", "100-0001"),
            # Unlisted countries fall back to the permissive pattern.
            ("BR", "01310-100"),
        ],
    )
    def test_accepts_known_postal_formats(self, validator, country_code, postal_code) -> None:
        validated = validator.validate(
            _address(country_code=country_code, postal_code=postal_code)
        )

        assert validated.postal_code == postal_code


class TestRejectedAddresses:
    def test_missing_address_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="missing"):
            validator.validate(None)

    def test_reports_every_problem_at_once(self, validator) -> None:
        with pytest.raises(CJAddressValidationError) as error:
            validator.validate(
                _address(city="", postal_code="99999", country_code="US", phone="12")
            )

        detail = error.value.detail
        assert "missing city" in detail
        assert "phone number must contain" in detail

    def test_wrong_postal_code_for_country_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="postal code"):
            validator.validate(_address(country_code="US", postal_code="M5V 2T6"))

    def test_street_without_house_number_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="house or building number"):
            validator.validate(_address(street="Test Street"))

    def test_po_box_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="PO box"):
            validator.validate(_address(street="P.O. Box 1234"))

    def test_po_box_is_allowed_when_disabled(self, validator) -> None:
        validator.settings.CJ_DROPSHIPPING_REJECT_PO_BOX_ADDRESSES = False

        validated = validator.validate(_address(street="P.O. Box 1234"))

        assert validated.street == "P.O. Box 1234"

    def test_non_iso_country_code_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="2-letter ISO code"):
            validator.validate(_address(country_code="CAN"))

    def test_unsupported_country_is_rejected(self, validator) -> None:
        validator.settings.CJ_DROPSHIPPING_SUPPORTED_COUNTRY_CODES = ["us", "gb"]

        with pytest.raises(CJAddressValidationError, match="not served"):
            validator.validate(_address())

    def test_oversized_field_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="250-character limit"):
            validator.validate(_address(street="1 " + "a" * 260))

    def test_phone_with_too_many_digits_is_rejected(self, validator) -> None:
        with pytest.raises(CJAddressValidationError, match="phone number"):
            validator.validate(_address(phone="1234567890123456789"))
