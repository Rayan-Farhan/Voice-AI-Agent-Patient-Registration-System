import hmac
import logging

from fastapi import Header, HTTPException, Query, Request, status

from app.config import get_settings
from app.db import get_db

logger = logging.getLogger(__name__)

__all__ = ["get_db", "verify_vapi_secret"]


def verify_vapi_secret(
    request: Request,
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
        # Logged because a silently rejected webhook is indistinguishable from
        # one that was never sent, and the two have very different fixes.
        logger.warning(
            "vapi_auth_rejected path=%s reason=%s",
            request.url.path,
            "no secret supplied" if not provided else "secret mismatch",
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing Vapi secret")
