"""Client for the official Companies House REST API."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Callable, Optional, Union

import httpx

from ._http import RateLimit, Transport
from .errors import AUTH_HINT, AuthError

BASE_URL = "https://api.company-information.service.gov.uk"
MAX_PAGE = 100


def normalise_number(number: Union[str, int]) -> str:
    """'445790' -> '00445790', ' sc123456 ' -> 'SC123456'."""
    text = str(number).strip().upper()
    if not text:
        raise ValueError("company number is empty")
    return text.zfill(8) if text.isdigit() else text


class CompaniesHouse:
    """Synchronous client. Returns the API's JSON as plain dicts.

    Waits for the rate-limit window to reset when the remaining budget is low, retries
    429 and 502/503/504 a bounded number of times, and raises NotFound, AuthError,
    RateLimited or APIError otherwise.
    """

    def __init__(
        self,
        api_key: str,
        *,
        max_retries: int = 3,
        low_watermark: int = 5,
        max_wait: float = 310.0,
        timeout: float = 30.0,
        clock: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        import time

        if not api_key or not api_key.strip():
            raise AuthError("No Companies House API key given. " + AUTH_HINT)
        self._t = Transport(
            BASE_URL, {}, auth=httpx.BasicAuth(api_key, ""), auth_hint=AUTH_HINT,
            max_retries=max_retries, low_watermark=low_watermark, max_wait=max_wait,
            timeout=timeout, clock=clock or time.time, sleep=sleep or time.sleep,
            transport=transport,
        )

    @property
    def rate_limit(self) -> RateLimit:
        """The most recent X-Ratelimit-* state reported by the server."""
        return self._t.rate_limit

    def close(self) -> None:
        self._t.close()

    def __enter__(self) -> CompaniesHouse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: Any) -> dict:
        return self._t.request("GET", path, params={k: v for k, v in params.items()
                                                    if v is not None})

    # -- single calls -----------------------------------------------------------

    def company(self, number: Union[str, int]) -> dict:
        return self._get(f"/company/{normalise_number(number)}")

    def search(self, query: str, *, items_per_page: Optional[int] = None,
               start_index: Optional[int] = None) -> dict:
        return self._get("/search/companies", q=query, items_per_page=items_per_page,
                         start_index=start_index)

    def officers(self, number: Union[str, int], *, items_per_page: Optional[int] = None,
                 start_index: Optional[int] = None) -> dict:
        return self._get(f"/company/{normalise_number(number)}/officers",
                         items_per_page=items_per_page, start_index=start_index)

    def psc(self, number: Union[str, int], *, items_per_page: Optional[int] = None,
            start_index: Optional[int] = None) -> dict:
        return self._get(f"/company/{normalise_number(number)}/persons-with-significant-control",
                         items_per_page=items_per_page, start_index=start_index)

    def filing_history(self, number: Union[str, int], category: Optional[str] = None, *,
                       items_per_page: Optional[int] = None,
                       start_index: Optional[int] = None) -> dict:
        return self._get(f"/company/{normalise_number(number)}/filing-history",
                         category=category, items_per_page=items_per_page,
                         start_index=start_index)

    def charges(self, number: Union[str, int], *, items_per_page: Optional[int] = None,
                start_index: Optional[int] = None) -> dict:
        return self._get(f"/company/{normalise_number(number)}/charges",
                         items_per_page=items_per_page, start_index=start_index)

    # -- paging -----------------------------------------------------------------

    def _iter(self, fetch: Callable[..., dict], page_size: int,
              limit: Optional[int]) -> Iterator[dict]:
        page_size = max(1, min(page_size, MAX_PAGE))
        start, yielded = 0, 0
        while True:
            page = fetch(items_per_page=page_size, start_index=start)
            items = page.get("items") or []
            for item in items:
                yield item
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            start += len(items)
            total = page.get("total_results", page.get("total_count"))
            if not items or (total is not None and start >= total):
                return

    def iter_search(self, query: str, *, page_size: int = MAX_PAGE,
                    limit: Optional[int] = None) -> Iterator[dict]:
        """Yield search results, paging with start_index. Pass limit: a broad query can
        match hundreds of thousands of companies."""
        return self._iter(lambda **p: self.search(query, **p), page_size, limit)

    def iter_officers(self, number: Union[str, int], *, page_size: int = MAX_PAGE,
                      limit: Optional[int] = None) -> Iterator[dict]:
        return self._iter(lambda **p: self.officers(number, **p), page_size, limit)

    def iter_psc(self, number: Union[str, int], *, page_size: int = MAX_PAGE,
                 limit: Optional[int] = None) -> Iterator[dict]:
        return self._iter(lambda **p: self.psc(number, **p), page_size, limit)

    def iter_filing_history(self, number: Union[str, int], category: Optional[str] = None, *,
                            page_size: int = MAX_PAGE,
                            limit: Optional[int] = None) -> Iterator[dict]:
        return self._iter(lambda **p: self.filing_history(number, category, **p),
                          page_size, limit)

    def iter_charges(self, number: Union[str, int], *, page_size: int = MAX_PAGE,
                     limit: Optional[int] = None) -> Iterator[dict]:
        return self._iter(lambda **p: self.charges(number, **p), page_size, limit)
