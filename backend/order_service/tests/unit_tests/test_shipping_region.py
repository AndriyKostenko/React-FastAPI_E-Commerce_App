"""The Canada-only rule every shipping address passes before an order is priced."""

import pytest

from shared.contracts.shipping_region import CanadianAddress, NotShippableError


def _normalise(**overrides: str | None) -> CanadianAddress:
    values: dict[str, str | None] = dict(country=None, country_code="CA", province="AB", postal_code="T2T 2T2")
    return CanadianAddress.normalise(**{**values, **overrides})


@pytest.mark.parametrize(
    ("province", "code"),
    [("AB", "AB"), ("ab", "AB"), ("Alberta", "AB"), ("  british   columbia ", "BC"),
     ("Québec", "QC"), ("Quebec", "QC"), ("Newfoundland", "NL"), ("PEI", "PE"), ("YT", "YT")],
)
def test_every_way_of_writing_a_province_becomes_its_code(province: str, code: str) -> None:
    assert _normalise(province=province).province_code == code


@pytest.mark.parametrize("postal_code", ["t2t2t2", "T2T 2T2", "T2T-2T2", " t2t  2t2 "])
def test_postal_codes_come_out_as_A1A_1A1(postal_code: str) -> None:
    assert _normalise(postal_code=postal_code).postal_code == "T2T 2T2"


@pytest.mark.parametrize(
    ("country", "country_code"),
    [(None, None), ("Canada", None), ("canada", "ca"), (None, "CA"), ("CAN", None)],
)
def test_canada_however_it_is_written_or_left_out(country: str | None, country_code: str | None) -> None:
    address = _normalise(country=country, country_code=country_code)
    assert (address.country, address.country_code) == ("Canada", "CA")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"country_code": "US"}, "only ship within Canada"),
        ({"country": "United States", "country_code": None}, "only ship within Canada"),
        # A Canadian code with a foreign name is contradictory, not Canadian.
        ({"country": "France"}, "only ship within Canada"),
        ({"province": "WA"}, "not a Canadian province"),
        ({"province": "Ontari0"}, "not a Canadian province"),
        ({"postal_code": "98101"}, "not a Canadian postal code"),
        ({"postal_code": "SW1A 1AA"}, "not a Canadian postal code"),
        # D, F, I, O, Q, U are never used; W and Z never lead.
        ({"postal_code": "D2T 2T2"}, "not a Canadian postal code"),
        ({"postal_code": "W2T 2T2"}, "not a Canadian postal code"),
    ],
)
def test_anything_outside_canada_is_refused(overrides: dict[str, str | None], message: str) -> None:
    with pytest.raises(NotShippableError, match=message):
        _normalise(**overrides)
