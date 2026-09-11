"""Field-level validation shared by the REST API and the voice agent's tools.

These live apart from the Pydantic schemas so the same rules can be reused in
error messages spoken back to a caller, which need to name the offending field
rather than return a JSON error body.
"""

import re
from datetime import date, datetime

# Postal abbreviations for the 50 states, DC and the inhabited territories that
# use the USPS addressing system.
US_STATES = frozenset(
    """AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS
    MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI
    WY DC AS GU MP PR VI""".split()
)

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z' \-]*$")
ZIP_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")

SEX_VALUES = ("Male", "Female", "Other", "Decline to Answer")


def normalize_phone(value: str) -> str:
    """Reduce any spoken or written US number to its 10 digits.

    Callers say numbers in wildly varying shapes ("(415) 555-0142", "+1 415 555
    0142", "415.555.0142"). Storing a single canonical form is what makes
    duplicate detection an exact-match lookup rather than a fuzzy search.
    """
    digits = re.sub(r"\D", "", value)

    # A leading country code is the one prefix worth tolerating; anything else
    # of the wrong length is a transcription error the agent should re-ask for.
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        raise ValueError("Phone number must be a 10-digit US number")
    if digits[0] in "01":
        raise ValueError("US area codes cannot begin with 0 or 1")

    return digits


def validate_name(value: str, field: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 50:
        raise ValueError(f"{field} must be between 1 and 50 characters")
    if not NAME_PATTERN.match(value):
        raise ValueError(f"{field} may only contain letters, hyphens and apostrophes")
    return value


def parse_date_of_birth(value: object) -> object:
    """Accept MM/DD/YYYY as well as ISO dates.

    The brief specifies MM/DD/YYYY, which is also what a US caller says aloud
    and what an LLM is most likely to emit unprompted. Pydantic only parses ISO
    by default, so both forms are normalised here before field validation.
    Anything else is passed through untouched for Pydantic to reject.
    """
    if not isinstance(value, str):
        return value

    value = value.strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return value


def validate_text(value: str, field: str, max_length: int) -> str:
    """Bound a free-text field so an over-long value fails validation rather
    than the database write, which would surface as a 500 instead of a 422."""
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer")
    return value


def validate_date_of_birth(value: date) -> date:
    if value > date.today():
        raise ValueError("Date of birth cannot be in the future")
    # Guards against a mis-heard year (e.g. "1090") reaching the database.
    if value.year < 1900:
        raise ValueError("Date of birth must be after 1900")
    return value


def validate_state(value: str) -> str:
    value = value.strip().upper()
    if value not in US_STATES:
        raise ValueError("State must be a valid 2-letter US abbreviation")
    return value


def validate_zip_code(value: str) -> str:
    value = value.strip()
    if not ZIP_PATTERN.match(value):
        raise ValueError("ZIP code must be 5 digits or ZIP+4 format")
    return value
