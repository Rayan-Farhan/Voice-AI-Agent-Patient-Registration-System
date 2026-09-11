"""Exception handlers that force every response into the mandated envelope.

FastAPI's defaults return bare bodies such as {"detail": ...}. The brief
requires {"data": ..., "error": ...} on every response, so each error class is
re-wrapped here rather than at each call site.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.patients import PatientNotFoundError

logger = logging.getLogger(__name__)


def _envelope(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": None, "error": message})


def _format_validation_errors(exc: RequestValidationError) -> str:
    """Flatten Pydantic's error list into one readable sentence.

    The voice agent relays this string to the caller, so it has to name the
    offending field in plain language rather than dump a nested structure.
    """
    parts = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"] if loc not in ("body", "query"))
        parts.append(f"{field}: {err['msg']}" if field else err["msg"])
    return "; ".join(parts)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PatientNotFoundError)
    async def _not_found(request: Request, exc: PatientNotFoundError) -> JSONResponse:
        return _envelope(status.HTTP_404_NOT_FOUND, f"No patient found with id {exc}")

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(status.HTTP_422_UNPROCESSABLE_ENTITY, _format_validation_errors(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the detail, return a generic message: internals must not leak to
        # an API client, and certainly not to a caller on the phone.
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return _envelope(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
