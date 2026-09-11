"""Patient persistence and query logic.

Both the public REST routes and the voice agent's tool endpoints call into
this module, so validation and soft-delete semantics cannot drift between the
two entry points.
"""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Patient
from app.schemas import PatientCreate, PatientUpdate
from app.validators import normalize_phone

logger = logging.getLogger(__name__)


class PatientNotFoundError(Exception):
    """Raised when a patient_id matches nothing, or matches a deleted record."""


def _active(stmt):
    """Soft-deleted rows are invisible to every read path.

    Applied centrally rather than per-query so a new caller cannot forget it and
    silently resurrect deleted patients.
    """
    return stmt.where(Patient.deleted_at.is_(None))


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)

    logger.info(
        "patient_created id=%s name=%s %s phone=%s",
        patient.patient_id,
        patient.first_name,
        patient.last_name,
        patient.phone_number,
    )
    return patient


def get_patient(db: Session, patient_id: str) -> Patient:
    patient = db.scalar(_active(select(Patient).where(Patient.patient_id == patient_id)))
    if patient is None:
        raise PatientNotFoundError(patient_id)
    return patient


def list_patients(
    db: Session,
    last_name: str | None = None,
    date_of_birth: date | None = None,
    phone_number: str | None = None,
) -> list[Patient]:
    stmt = _active(select(Patient))

    if last_name:
        stmt = stmt.where(Patient.last_name.ilike(last_name))
    if date_of_birth:
        stmt = stmt.where(Patient.date_of_birth == date_of_birth)
    if phone_number:
        # Normalise the query the same way we normalised storage, so a caller
        # can filter with "(415) 555-0142" and still match.
        stmt = stmt.where(Patient.phone_number == normalize_phone(phone_number))

    return list(db.scalars(stmt.order_by(Patient.created_at.desc())))


def find_by_phone(db: Session, phone_number: str) -> Patient | None:
    """Duplicate detection for returning callers."""
    return db.scalar(
        _active(select(Patient).where(Patient.phone_number == normalize_phone(phone_number)))
    )


def update_patient(db: Session, patient_id: str, payload: PatientUpdate) -> Patient:
    patient = get_patient(db, patient_id)

    # exclude_unset keeps PUT partial: an omitted field is left alone rather
    # than being overwritten with None.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    logger.info("patient_updated id=%s", patient.patient_id)
    return patient


def soft_delete_patient(db: Session, patient_id: str) -> Patient:
    patient = get_patient(db, patient_id)
    patient.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patient)
    logger.info("patient_soft_deleted id=%s", patient.patient_id)
    return patient
