from datetime import date, timedelta

import pytest

from app.validators import (
    normalize_phone,
    validate_date_of_birth,
    validate_name,
    validate_state,
    validate_zip_code,
)


@pytest.mark.parametrize(
    "spoken",
    ["(415) 555-0142", "415-555-0142", "+1 415 555 0142", "415.555.0142", "4155550142"],
)
def test_phone_formats_normalize_to_ten_digits(spoken):
    """Speech-to-text yields inconsistent formatting; storage must be canonical."""
    assert normalize_phone(spoken) == "4155550142"


@pytest.mark.parametrize("bad", ["555", "41555501423", "0155550142"])
def test_invalid_phone_rejected(bad):
    with pytest.raises(ValueError):
        normalize_phone(bad)


def test_future_date_of_birth_rejected():
    with pytest.raises(ValueError, match="future"):
        validate_date_of_birth(date.today() + timedelta(days=1))


def test_implausible_birth_year_rejected():
    with pytest.raises(ValueError):
        validate_date_of_birth(date(1090, 1, 1))


def test_names_allow_hyphens_and_apostrophes():
    assert validate_name("O'Brien-Smith", "Last name") == "O'Brien-Smith"


def test_name_with_digits_rejected():
    with pytest.raises(ValueError):
        validate_name("Jane2", "First name")


def test_state_is_uppercased_and_checked():
    assert validate_state("ca") == "CA"
    with pytest.raises(ValueError):
        validate_state("XX")


@pytest.mark.parametrize("zip_code", ["94110", "94110-1234"])
def test_zip_accepts_five_and_plus_four(zip_code):
    assert validate_zip_code(zip_code) == zip_code


def test_malformed_zip_rejected():
    with pytest.raises(ValueError):
        validate_zip_code("941")


@pytest.mark.parametrize("spoken", ["03/12/1985", "3/12/1985", "03-12-1985"])
def test_us_date_formats_are_converted(spoken):
    """The brief specifies MM/DD/YYYY; Pydantic parses only ISO by default."""
    from app.validators import parse_date_of_birth

    assert parse_date_of_birth(spoken) == date(1985, 3, 12)


@pytest.mark.parametrize("passthrough", ["1985-03-12", "not-a-date"])
def test_non_us_formats_pass_through_untouched(passthrough):
    """ISO is Pydantic's job; anything unparseable is left for it to reject."""
    from app.validators import parse_date_of_birth

    assert parse_date_of_birth(passthrough) == passthrough


def test_text_field_is_bounded_and_non_empty():
    from app.validators import validate_text

    assert validate_text("  San Francisco ", "City", 100) == "San Francisco"
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_text("   ", "City", 100)
    with pytest.raises(ValueError, match="100 characters"):
        validate_text("x" * 101, "City", 100)
