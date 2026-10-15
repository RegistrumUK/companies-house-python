"""Shared HTTP layer: auth, user-agent, rate-limit awareness, bounded retries."""
from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx

from ._version import __version__
from .errors import (
    AUTH_HINT,
    APIError,
    AuthError,
    NotFound,
    RateLimited,
    TrialUnverified,
)

USER_AGENT = (
    f"companies-house-python/{__version__} "
    "(+https://github.com/RegistrumUK/companies-house-python)"
)
RETRY_STATUSES = (502, 503, 504)
# X-Ratelimit-Reset is epoch seconds on both APIs (captured 2026-10-15). A small value is
# treated as "seconds from now" so a change of convention fails safe rather than sleeping
# for fifty years.
EPOCH_THRESHOLD = 1_000_000_000


@dataclass
class RateLimit:
    """The last rate-limit state the server told us about. None means not seen yet."""

    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset: Optional[float] = None  # epoch seconds
    window: Optional[str] = None


def _int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


class Transport:
    def __init__(
        self,
        base_url: str,
        headers: Mapping[str, str],
        *,
        auth: Optional[httpx.Auth] = None,
        auth_hint: str = "",
        max_retries: int = 3,
        low_watermark: int = 5,
        max_wait: float = 310.0,
        timeout: float = 30.0,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.max_retries = max_retries
        self.low_watermark = low_watermark
        self.max_wait = max_wait
        self.clock = clock
        self.sleep = sleep
        self.auth_hint = auth_hint
        self.rate_limit = RateLimit()
        self.headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **headers}
        self.http = httpx.Client(base_url=base_url, auth=auth, timeout=timeout,
                                 transport=transport)

    def close(self) -> None:
        self.http.close()

    # -- rate limit bookkeeping -------------------------------------------------

    def _seconds_until_reset(self) -> Optional[float]:
        reset = self.rate_limit.reset
        if reset is None:
            return None
        return reset - self.clock() if reset > EPOCH_THRESHOLD else reset

    def _observe(self, headers: httpx.Headers) -> None:
        rl = self.rate_limit
        rl.limit = _int(headers.get("x-ratelimit-limit"))
        remaining = headers.get("x-ratelimit-remain", headers.get("x-ratelimit-remaining"))
        rl.remaining = _int(remaining)
        reset = _int(headers.get("x-ratelimit-reset"))
        if reset is not None:
            rl.reset = float(reset) if reset > EPOCH_THRESHOLD else self.clock() + reset
        rl.window = headers.get("x-ratelimit-window")

    def _wait_before_request(self) -> None:
        """Sleep until the window resets when we are nearly out of budget, so the next
        call does not earn a 429. A wait longer than max_wait (a monthly quota, say) is
        not slept: the server will answer for itself."""
        rl = self.rate_limit
        if rl.remaining is None or rl.remaining > self.low_watermark:
            return
        wait = self._seconds_until_reset()
        if wait is not None and 0 < wait <= self.max_wait:
            self.sleep(wait + 1)  # +1s: the server's clock may be slightly ahead of ours
            self.rate_limit = RateLimit(limit=rl.limit, window=rl.window)

    def _retry_after(self, resp: httpx.Response) -> Optional[float]:
        header = resp.headers.get("retry-after")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
        wait = self._seconds_until_reset()
        return max(wait, 1.0) if wait is not None else None

    # -- request ----------------------------------------------------------------

    def request(self, method: str, path: str, *, params: Optional[dict] = None,
                json: Any = None, send_auth: bool = True) -> Any:
        attempt = 0
        while True:
            self._wait_before_request()
            try:
                resp = self.http.request(
                    method, path, params=params, json=json,
                    headers=self.headers if send_auth else {"User-Agent": USER_AGENT,
                                                            "Accept": "application/json"},
                    auth=self.http.auth if send_auth else None,
                )
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise APIError(f"Network error: {exc}") from exc
                self.sleep(self._backoff(attempt))
                attempt += 1
                continue
            self._observe(resp.headers)

            if resp.status_code == 429:
                wait = self._retry_after(resp)
                if wait is None:
                    wait = self._backoff(attempt)
                if wait > self.max_wait or attempt >= self.max_retries:
                    raise RateLimited(
                        f"Rate limited (HTTP 429); the server asks for a wait of {wait:.0f}s.",
                        retry_after=wait, body=_body(resp))
                self.sleep(wait + 1)
                self.rate_limit = RateLimit(limit=self.rate_limit.limit,
                                            window=self.rate_limit.window)
                attempt += 1
                continue

            if resp.status_code in RETRY_STATUSES:
                if attempt >= self.max_retries:
                    raise APIError(f"HTTP {resp.status_code} after {attempt + 1} attempts.",
                                   resp.status_code, _body(resp))
                self.sleep(self._backoff(attempt))
                attempt += 1
                continue

            if resp.status_code >= 400:
                self._raise(resp)
            return resp.json()

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(0.5 * (2 ** attempt), 30.0)

    def _raise(self, resp: httpx.Response) -> None:
        body = _body(resp)
        message = _message(body) or f"HTTP {resp.status_code}"
        status = resp.status_code
        if status == 404:
            raise NotFound(message, status, body)
        if status == 403 and isinstance(body, dict) and body.get("error_code") == "TRIAL_UNVERIFIED":
            raise TrialUnverified(message, status, body)
        if status in (401, 403):
            raise AuthError(f"{message}. {self.auth_hint or AUTH_HINT}", status, body)
        raise APIError(message, status, body)


def _body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text


def _message(body: Any) -> str:
    if isinstance(body, dict):
        for key in ("detail", "error", "message"):
            if isinstance(body.get(key), str):
                return body[key]
    return body if isinstance(body, str) else ""
