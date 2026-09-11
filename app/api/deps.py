import hmac

from fastapi import Header, HTTPException, Query, status

from app.config import get_settings
from app.db import get_db

__all__ = ["get_db", "verify_vapi_secret"]


def verify_vapi_secret(
    x_vapi_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
) -> None:
    """Reject tool calls that do not carry the shared secret.

    The tool endpoints are public write endpoints on the open internet, so
    something has to gate them. Vapi sends whatever is configured under the
    assistant's server headers; the query parameter is a fallback for setups
    where custom headers are awkward to configure.

    compare_digest rather than == to avoid leaking the secret by timing.
    """
    expected = get_settings().vapi_shared_secret
    provided = x_vapi_secret or secret or ""

    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing Vapi secret")
