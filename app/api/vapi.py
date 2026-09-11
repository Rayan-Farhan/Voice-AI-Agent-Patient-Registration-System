"""Webhook endpoints the Vapi assistant calls during a conversation.

Tool results are returned as short natural-language strings because the LLM
reads them straight out to the caller. In particular, validation failures are
translated into a sentence naming the offending field, which is what lets the
agent re-prompt for just that field instead of restarting the whole intake.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_vapi_secret
from app.schemas import PatientCreate, PatientUpdate
from app.services import call_sessions, patients as service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vapi", tags=["vapi"], dependencies=[Depends(verify_vapi_secret)])


def _spoken_validation_error(exc: ValidationError) -> str:
    """Turn Pydantic's error list into one sentence an agent can say aloud."""
    problems = []
    for err in exc.errors():
        field = str(err["loc"][0]).replace("_", " ") if err["loc"] else "input"
        message = err["msg"].removeprefix("Value error, ")
        problems.append(f"{field}: {message}")
    return "That didn't validate - " + "; ".join(problems)


def _describe(patient) -> dict[str, Any]:
    return {
        "patient_id": patient.patient_id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth.isoformat(),
        "phone_number": patient.phone_number,
    }


def _lookup_patient_by_phone(db: Session, args: dict, call_id: str) -> Any:
    phone = args.get("phone_number", "")
    try:
        existing = service.find_by_phone(db, phone)
    except ValueError as exc:
        return str(exc)

    if existing is None:
        return {"found": False, "message": "No existing record for that number."}

    return {
        "found": True,
        "patient": _describe(existing),
        "message": (
            f"An existing record was found for {existing.first_name} "
            f"{existing.last_name}. Offer to update it instead of creating a new one."
        ),
    }


def _create_patient(db: Session, args: dict, call_id: str) -> Any:
    try:
        payload = PatientCreate(**args)
    except ValidationError as exc:
        return _spoken_validation_error(exc)

    patient = service.create_patient(db, payload)
    call_sessions.attach_patient(db, call_id, patient.patient_id)

    return {
        "success": True,
        "patient_id": patient.patient_id,
        "message": f"Registration saved for {patient.first_name} {patient.last_name}.",
    }


def _update_patient(db: Session, args: dict, call_id: str) -> Any:
    patient_id = args.pop("patient_id", None)
    if not patient_id:
        return "A patient_id is required to update a record."

    try:
        payload = PatientUpdate(**args)
    except ValidationError as exc:
        return _spoken_validation_error(exc)

    try:
        patient = service.update_patient(db, patient_id, payload)
    except service.PatientNotFoundError:
        return "No record exists with that id."

    call_sessions.attach_patient(db, call_id, patient.patient_id)
    return {"success": True, "message": f"Record updated for {patient.first_name}."}


HANDLERS = {
    "lookup_patient_by_phone": _lookup_patient_by_phone,
    "create_patient": _create_patient,
    "update_patient": _update_patient,
}


@router.post("/tools")
async def handle_tool_calls(request: Request, db: Session = Depends(get_db)) -> dict:
    """Dispatch one or more tool calls from the assistant.

    Vapi batches calls into message.toolCallList and expects a results array
    keyed by toolCallId. Errors are returned as spoken text with a 200 rather
    than an HTTP error status: a non-2xx leaves the agent with nothing to say
    to the caller, which is exactly the dead-air failure to avoid.
    """
    body = await request.json()
    message = body.get("message", {})
    call_id = (message.get("call") or {}).get("id", "unknown")

    # toolCalls is the older key name; accept both so a Vapi-side change or an
    # older assistant config does not silently break every call.
    tool_calls = message.get("toolCallList") or message.get("toolCalls") or []

    results = []
    for call in tool_calls:
        name = call.get("name") or call.get("function", {}).get("name")
        args = call.get("arguments") or call.get("function", {}).get("arguments") or {}

        logger.info("tool_call call_id=%s tool=%s args=%s", call_id, name, args)
        call_sessions.record_progress(db, call_id, collected=args)

        handler = HANDLERS.get(name)
        if handler is None:
            result: Any = f"Unknown tool {name}."
        else:
            try:
                result = handler(db, dict(args), call_id)
            except Exception:
                # The caller is mid-conversation; give the agent something
                # graceful to say rather than letting the turn fail silently.
                logger.exception("tool %s failed for call_id=%s", name, call_id)
                result = (
                    "Something went wrong saving that. Apologise, and offer to "
                    "try again in a moment."
                )

        logger.info("tool_result call_id=%s tool=%s result=%s", call_id, name, result)
        results.append({"toolCallId": call.get("id"), "result": result})

    return {"results": results}


@router.post("/events")
async def handle_call_events(request: Request, db: Session = Depends(get_db)) -> dict:
    """Persist the transcript from Vapi's end-of-call report."""
    message = (await request.json()).get("message", {})

    if message.get("type") != "end-of-call-report":
        return {"received": True}

    call_id = (message.get("call") or {}).get("id")
    if call_id:
        call_sessions.save_transcript(db, call_id, message.get("transcript", ""))
        logger.info("call_ended call_id=%s reason=%s", call_id, message.get("endedReason"))

    return {"received": True}
