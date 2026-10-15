"""Capture REAL responses from both APIs into tests/fixtures/.

Never hand-author a fixture for an external API: the shapes and the X-Ratelimit-*
headers are exactly what the tests exist to pin. Run this to refresh them.

    CH_API_KEY=<companies house rest key> REGISTRUM_API_KEY=<key> python scripts/capture_fixtures.py

Keys come from the environment only and are never written out. Authorization and
X-API-Key are not stored; only headers that matter to client behaviour are kept.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

CH = "https://api.company-information.service.gov.uk"
REG = "https://api.registrum.co.uk"
REFERENCE = "00445790"  # Tesco PLC
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
KEEP = ("content-type", "retry-after", "x-ratelimit-")
UA = "companies-house-python-fixture-capture"


def save(name: str, resp: httpx.Response) -> None:
    headers = {k.lower(): v for k, v in resp.headers.items() if k.lower().startswith(KEEP)}
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    record = {"url": str(resp.request.url), "status": resp.status_code, "headers": headers,
              "body": body}
    (OUT / f"{name}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")
    print(f"{name}: {resp.status_code} {sorted(headers)}")


def main() -> int:
    ch_key, reg_key = os.environ.get("CH_API_KEY"), os.environ.get("REGISTRUM_API_KEY")
    if not ch_key or not reg_key:
        print("Set CH_API_KEY and REGISTRUM_API_KEY", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    h = {"User-Agent": UA}
    with httpx.Client(timeout=30, headers=h) as c:
        auth = httpx.BasicAuth(ch_key, "")
        ch = {
            "ch_company": f"/company/{REFERENCE}",
            "ch_search": "/search/companies?q=tesco&items_per_page=2&start_index=0",
            "ch_search_page2": "/search/companies?q=tesco&items_per_page=2&start_index=2",
            "ch_officers": f"/company/{REFERENCE}/officers?items_per_page=3",
            "ch_psc": f"/company/{REFERENCE}/persons-with-significant-control",
            "ch_filing_history": f"/company/{REFERENCE}/filing-history?items_per_page=3&category=accounts",
            "ch_charges": f"/company/{REFERENCE}/charges",
            "ch_not_found": "/company/99999999",
        }
        for name, path in ch.items():
            save(name, c.get(CH + path, auth=auth))
        save("ch_unauthorized", c.get(CH + f"/company/{REFERENCE}",
                                      auth=httpx.BasicAuth("00000000-0000-0000-0000-000000000000", "")))
        rh = {"X-API-Key": reg_key}
        reg = {
            "reg_company": f"/v1/company/{REFERENCE}",
            "reg_search": "/v1/search?q=tesco&items_per_page=2",
            "reg_financials": f"/v1/company/{REFERENCE}/financials",
            "reg_psc_chain": f"/v1/company/{REFERENCE}/psc/chain?max_depth=2",
            "reg_bundle": f"/v1/company/{REFERENCE}/bundle?include=profile,financials",
            "reg_not_found": "/v1/company/99999999",
        }
        for name, path in reg.items():
            save(name, c.get(REG + path, headers=rh))
        save("reg_unauthorized", c.get(REG + f"/v1/company/{REFERENCE}",
                                       headers={"X-API-Key": "reg_invalid_key_for_fixture"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
