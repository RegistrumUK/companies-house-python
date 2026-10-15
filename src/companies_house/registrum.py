"""Client for the Registrum API: the same company data plus financials and ownership chains."""
from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Callable, Optional, Union

import httpx

from ._http import RateLimit, Transport
from .companies_house import normalise_number
from .errors import AuthError

BASE_URL = "https://api.registrum.co.uk"
NO_KEY = (
    "No Registrum API key. Pass api_key=..., set REGISTRUM_API_KEY, or call "
    "Registrum().start_trial('you@example.com') to get one (you must click the link we "
    "email before it works)."
)


class Registrum:
    """Same shape as CompaniesHouse. Methods return the `data` payload of Registrum's
    response envelope as a plain dict."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        max_retries: int = 3,
        low_watermark: int = 5,
        max_wait: float = 310.0,
        timeout: float = 60.0,
        clock: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        import time

        self.api_key = api_key or os.environ.get("REGISTRUM_API_KEY")
        self._t = Transport(
            BASE_URL, {}, max_retries=max_retries, low_watermark=low_watermark,
            max_wait=max_wait, timeout=timeout, clock=clock or time.time,
            sleep=sleep or time.sleep, transport=transport,
            auth_hint="Check the key at https://registrum.co.uk/dashboard.",
        )

    @property
    def rate_limit(self) -> RateLimit:
        return self._t.rate_limit

    def close(self) -> None:
        self._t.close()

    def __enter__(self) -> Registrum:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: object) -> dict:
        if not self.api_key:
            raise AuthError(NO_KEY)
        self._t.headers["X-API-Key"] = self.api_key
        body = self._t.request("GET", path, params={k: v for k, v in params.items()
                                                    if v is not None})
        return body.get("data", body) if isinstance(body, dict) else body

    def company(self, number: Union[str, int]) -> dict:
        return self._get(f"/v1/company/{normalise_number(number)}")

    def search(self, query: str, *, items_per_page: Optional[int] = None,
               start_index: Optional[int] = None) -> dict:
        return self._get("/v1/search", q=query, items_per_page=items_per_page,
                         start_index=start_index)

    def financials(self, number: Union[str, int]) -> dict:
        """Structured figures from filed accounts, which the official API does not return."""
        return self._get(f"/v1/company/{normalise_number(number)}/financials")

    def psc_chain(self, number: Union[str, int], *, max_depth: Optional[int] = None) -> dict:
        """Follow corporate persons with significant control up to the people behind them."""
        return self._get(f"/v1/company/{normalise_number(number)}/psc/chain",
                         max_depth=max_depth)

    def bundle(self, number: Union[str, int], include: Optional[Iterable[str]] = None) -> dict:
        """Profile, compliance, financials, PSC and directors in one request."""
        return self._get(f"/v1/company/{normalise_number(number)}/bundle",
                         include=",".join(include) if include is not None else None)

    def start_trial(self, email: str) -> dict:
        """Ask for a trial key with just an email (POST /v1/trial, source "pypi").

        The key is stored on this client but answers 403 (TrialUnverified) until you click
        the link emailed to you. Asking again for an address that already has a key raises
        APIError with status 409."""
        body = self._t.request("POST", "/v1/trial", json={"email": email, "source": "pypi"},
                               send_auth=False)
        self.api_key = body.get("api_key", self.api_key)
        return body
