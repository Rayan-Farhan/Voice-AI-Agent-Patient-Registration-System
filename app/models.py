import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Patient(Base):
    """A registered patient.

    Column types are deliberately engine-neutral - UUIDs as strings, timestamps
    as timezone-aware DateTime - so the same model runs on SQLite locally and
    Postgres in production without a dialect-specific branch.
    """

    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)

    # Stored as 10 bare digits; see validators.normalize_phone.
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))

    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    insurance_provider: Mapped[str | None] = mapped_column(String(150))
    insurance_member_id: Mapped[str | None] = mapped_column(String(50))
    preferred_language: Mapped[str] = mapped_column(String(50), default="English")

    emergency_contact_name: Mapped[str | None] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    # Soft-delete marker: records are retired, never removed.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_patients_phone_number", "phone_number"),
        Index("ix_patients_last_name", "last_name"),
    )


class CallSession(Base):
    """Per-call state captured as the conversation progresses.

    Written incrementally rather than only at the end so a dropped call leaves
    a recoverable record of what the caller had already given us, and so each
    registration can be traced back to the conversation that produced it.
    """

    __tablename__ = "call_sessions"

    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")

    # Partial payload, keyed by field name. JSON rather than columns because the
    # shape is whatever the caller has volunteered so far.
    collected_data: Mapped[dict] = mapped_column(JSON, default=dict)
    transcript: Mapped[str | None] = mapped_column(Text)

    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.patient_id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
