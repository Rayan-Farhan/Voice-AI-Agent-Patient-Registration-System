from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app import validators

Sex = Literal["Male", "Female", "Other", "Decline to Answer"]

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """The response shape the assessment mandates: {"data": ..., "error": ...}."""

    data: T | None = None
    error: str | None = None


class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str

    email: EmailStr | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name")
    @classmethod
    def _check_first_name(cls, v: str) -> str:
        return validators.validate_name(v, "First name")

    @field_validator("last_name")
    @classmethod
    def _check_last_name(cls, v: str) -> str:
        return validators.validate_name(v, "Last name")

    @field_validator("date_of_birth")
    @classmethod
    def _check_dob(cls, v: date) -> date:
        return validators.validate_date_of_birth(v)

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return validators.normalize_phone(v) if v else v

    @field_validator("state")
    @classmethod
    def _check_state(cls, v: str) -> str:
        return validators.validate_state(v)

    @field_validator("zip_code")
    @classmethod
    def _check_zip(cls, v: str) -> str:
        return validators.validate_zip_code(v)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    """Partial update: every field is optional, but supplied values still face
    the same validators as on create."""

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone_number: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    preferred_language: str | None = None

    @field_validator("first_name")
    @classmethod
    def _check_first_name(cls, v: str | None) -> str | None:
        return validators.validate_name(v, "First name") if v else v

    @field_validator("last_name")
    @classmethod
    def _check_last_name(cls, v: str | None) -> str | None:
        return validators.validate_name(v, "Last name") if v else v

    @field_validator("date_of_birth")
    @classmethod
    def _check_dob(cls, v: date | None) -> date | None:
        return validators.validate_date_of_birth(v) if v else v

    @field_validator("state")
    @classmethod
    def _check_state(cls, v: str | None) -> str | None:
        return validators.validate_state(v) if v else v

    @field_validator("zip_code")
    @classmethod
    def _check_zip(cls, v: str | None) -> str | None:
        return validators.validate_zip_code(v) if v else v


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    created_at: datetime
    updated_at: datetime


def as_dict(model: BaseModel) -> dict[str, Any]:
    """Supplied fields only - lets PUT distinguish "absent" from "set to null"."""
    return model.model_dump(exclude_unset=True)
