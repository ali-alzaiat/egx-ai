"""Shared-token API authentication for the single-user deployment.

Every router except health requires ``Authorization: Bearer <API_TOKEN>``.
An unset or too-short token fails closed: requests are refused rather than
served unauthenticated.
"""

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

MIN_API_TOKEN_LENGTH = 32

_bearer = HTTPBearer(auto_error=False)


def api_token_configured() -> bool:
    """True when API_TOKEN is long enough to be used as a credential."""
    return len(settings.API_TOKEN) >= MIN_API_TOKEN_LENGTH


async def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Reject the request unless it carries the configured bearer token."""
    if not api_token_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_TOKEN is not configured on the server",
        )
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode("utf-8"), settings.API_TOKEN.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
