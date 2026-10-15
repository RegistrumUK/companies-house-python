"""Exceptions. Everything raised for an HTTP outcome derives from APIError."""
from __future__ import annotations

from typing import Any, Optional

AUTH_HINT = (
    "Companies House uses HTTP Basic auth: your API key is the username with an empty password. "
    "Check that the key is a REST API key (not a Streaming or web/OAuth key) and that "
    "it was created for the live environment, not the sandbox."
)


class APIError(Exception):
    """The API answered with an error status (or kept failing with 5xx)."""

    def __init__(self, message: str, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class NotFound(APIError):
    """404: no such company or resource."""


class AuthError(APIError):
    """401/403, or a missing key."""


class TrialUnverified(AuthError):
    """Registrum 403 TRIAL_UNVERIFIED: the trial key exists but its emailed link was not
    clicked yet."""


class RateLimited(APIError):
    """429, and waiting was either not possible within max_wait or retries ran out.

    retry_after is the number of seconds the server asked us to wait, when known."""

    def __init__(self, message: str, retry_after: Optional[float] = None,
                 status: Optional[int] = 429, body: Any = None):
        super().__init__(message, status, body)
        self.retry_after = retry_after
