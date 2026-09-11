"""Per-call state, written as the conversation progresses.

Kept separate from patient persistence because its lifecycle is different: a
call session exists whether or not a registration ever completes, and it is
what survives a dropped connection.
"""

import logging

from sqlalchemy.orm import Session

from app.models import CallSession

logger = logging.getLogger(__name__)


def record_progress(
    db: Session, call_id: str, collected: dict | None = None, status: str | None = None
) -> CallSession:
    """Create or update the session for a call, merging newly collected fields."""
    session = db.get(CallSession, call_id)
    if session is None:
        session = CallSession(call_id=call_id, collected_data={})
        db.add(session)

    if collected:
        # Reassign rather than mutate: SQLAlchemy does not track in-place
        # changes to a JSON column.
        session.collected_data = {**(session.collected_data or {}), **collected}
    if status:
        session.status = status

    db.commit()
    db.refresh(session)
    return session


def attach_patient(db: Session, call_id: str, patient_id: str) -> None:
    session = record_progress(db, call_id, status="completed")
    session.patient_id = patient_id
    db.commit()


def save_transcript(db: Session, call_id: str, transcript: str) -> None:
    session = db.get(CallSession, call_id)
    if session is None:
        logger.warning("transcript for unknown call_id=%s", call_id)
        return

    session.transcript = transcript
    db.commit()
