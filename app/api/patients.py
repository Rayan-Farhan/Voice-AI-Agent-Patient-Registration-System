from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas import Envelope, PatientCreate, PatientOut, PatientUpdate
from app.services import patients as service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=Envelope[list[PatientOut]])
def list_patients(
    db: Session = Depends(get_db),
    last_name: str | None = Query(None),
    date_of_birth: date | None = Query(None),
    phone_number: str | None = Query(None),
) -> Envelope[list[PatientOut]]:
    records = service.list_patients(db, last_name, date_of_birth, phone_number)
    return Envelope(data=[PatientOut.model_validate(r) for r in records])


@router.get("/{patient_id}", response_model=Envelope[PatientOut])
def get_patient(patient_id: str, db: Session = Depends(get_db)) -> Envelope[PatientOut]:
    return Envelope(data=PatientOut.model_validate(service.get_patient(db, patient_id)))


@router.post("", response_model=Envelope[PatientOut], status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)) -> Envelope[PatientOut]:
    return Envelope(data=PatientOut.model_validate(service.create_patient(db, payload)))


@router.put("/{patient_id}", response_model=Envelope[PatientOut])
def update_patient(
    patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)
) -> Envelope[PatientOut]:
    return Envelope(data=PatientOut.model_validate(service.update_patient(db, patient_id, payload)))


@router.delete("/{patient_id}", response_model=Envelope[PatientOut])
def delete_patient(patient_id: str, db: Session = Depends(get_db)) -> Envelope[PatientOut]:
    """Soft-delete: the record is retired, never removed."""
    return Envelope(data=PatientOut.model_validate(service.soft_delete_patient(db, patient_id)))
