from __future__ import annotations

import base64

import pytest
from conftest import Script, load, reply

from companies_house import (
    APIError,
    AuthError,
    CompaniesHouse,
    NotFound,
    RateLimited,
    __version__,
)

UA = (f"companies-house-python/{__version__} "
      "(+https://github.com/RegistrumUK/companies-house-python)")


def client(script, clock, **kw):
    return CompaniesHouse("my-key", transport=script.transport, clock=clock.now,
                          sleep=clock.sleep, **kw)


def test_basic_auth_key_as_username_empty_password(clock):
    s = Script(reply("ch_company"))
    client(s, clock).company("00445790")
    sent = s.requests[0].headers["authorization"]
    assert sent == "Basic " + base64.b64encode(b"my-key:").decode()


def test_user_agent_is_stable(clock):
    s = Script(reply("ch_company"))
    client(s, clock).company("00445790")
    assert s.requests[0].headers["user-agent"] == UA


def test_company_returns_plain_dict_and_hits_official_host(clock):
    s = Script(reply("ch_company"))
    data = client(s, clock).company("00445790")
    assert data == load("ch_company")["body"]
    assert str(s.requests[0].url) == (
        "https://api.company-information.service.gov.uk/company/00445790")


@pytest.mark.parametrize("given,expected", [
    ("445790", "00445790"), (445790, "00445790"), (" sc123456 ", "SC123456"),
    ("00445790", "00445790"), ("ni000123", "NI000123"),
])
def test_company_numbers_are_normalised(clock, given, expected):
    s = Script(reply("ch_company"))
    client(s, clock).company(given)
    assert s.requests[0].url.path == f"/company/{expected}"


def test_empty_company_number_is_rejected_locally(clock):
    with pytest.raises(ValueError):
        client(Script(reply("ch_company")), clock).company("  ")


def test_search_params(clock):
    s = Script(reply("ch_search"))
    client(s, clock).search("tesco", items_per_page=2, start_index=0)
    r = s.requests[0]
    assert r.url.path == "/search/companies"
    assert dict(r.url.params) == {"q": "tesco", "items_per_page": "2", "start_index": "0"}


def test_resource_endpoints_paths_and_category(clock):
    s = Script(reply("ch_officers"), reply("ch_psc"), reply("ch_filing_history"),
               reply("ch_charges"))
    c = client(s, clock)
    c.officers("445790")
    c.psc("445790")
    c.filing_history("445790", category="accounts")
    c.charges("445790")
    assert [r.url.path for r in s.requests] == [
        "/company/00445790/officers",
        "/company/00445790/persons-with-significant-control",
        "/company/00445790/filing-history",
        "/company/00445790/charges",
    ]
    assert s.requests[2].url.params["category"] == "accounts"


def test_iter_search_pages_with_start_index_until_limit(clock):
    s = Script(reply("ch_search"), reply("ch_search_page2"))
    items = list(client(s, clock).iter_search("tesco", page_size=2, limit=4))
    assert len(items) == 4
    assert [r.url.params["start_index"] for r in s.requests] == ["0", "2"]
    assert all(r.url.params["items_per_page"] == "2" for r in s.requests)


def test_iter_stops_when_total_reached(clock):
    page = {"items": [{"n": 1}, {"n": 2}, {"n": 3}], "total_count": 3, "start_index": 0}
    s = Script(reply("ch_filing_history", body=page))
    items = list(client(s, clock).iter_filing_history("445790"))
    assert [i["n"] for i in items] == [1, 2, 3]
    assert len(s.requests) == 1


def test_iter_stops_on_empty_page(clock):
    first = {"items": [{"n": 1}], "total_results": 99}
    empty = {"items": [], "total_results": 99}
    s = Script(reply("ch_officers", body=first), reply("ch_officers", body=empty))
    assert len(list(client(s, clock).iter_officers("445790", page_size=1))) == 1
    assert len(s.requests) == 2


def test_low_remaining_sleeps_until_reset_before_next_call(clock):
    reset = clock.now() + 40
    low = {"x-ratelimit-remain": "2", "x-ratelimit-reset": str(int(reset))}
    s = Script(reply("ch_company", headers=low), reply("ch_company"))
    c = client(s, clock)
    c.company("445790")
    assert clock.slept == []          # nothing to wait for on the first call
    c.company("445790")
    assert len(clock.slept) == 1 and 40 <= clock.slept[0] <= 42
    assert len(s.requests) == 2       # and no 429 was ever provoked


def test_plenty_remaining_does_not_sleep(clock):
    s = Script(reply("ch_company"))
    c = client(s, clock)
    c.company("445790")
    c.company("445790")
    assert clock.slept == []


def test_wait_longer_than_max_wait_is_not_slept(clock):
    far = {"x-ratelimit-remain": "0", "x-ratelimit-reset": str(int(clock.now() + 99999))}
    s = Script(reply("ch_company", headers=far), reply("ch_company"))
    c = client(s, clock, max_wait=60)
    c.company("445790")
    c.company("445790")
    assert clock.slept == []


def test_429_honours_reset_header_then_succeeds(clock):
    reset = int(clock.now() + 25)
    limited = reply("ch_company", status=429, body={"error": "Too many requests"},
                    headers={"x-ratelimit-remain": "0", "x-ratelimit-reset": str(reset)})
    s = Script(limited, reply("ch_company"))
    data = client(s, clock).company("445790")
    assert data["company_number"] == "00445790"
    assert len(s.requests) == 2
    assert 25 <= clock.slept[0] <= 27


def test_429_prefers_retry_after(clock):
    limited = reply("ch_company", status=429, body={},
                    headers={"retry-after": "7", "x-ratelimit-remain": "0"})
    s = Script(limited, reply("ch_company"))
    client(s, clock).company("445790")
    assert 7 <= clock.slept[0] <= 9


def test_429_forever_raises_rate_limited_after_bounded_retries(clock):
    limited = reply("ch_company", status=429, body={},
                    headers={"retry-after": "3", "x-ratelimit-remain": "0"})
    s = Script(limited)
    with pytest.raises(RateLimited) as exc:
        client(s, clock, max_retries=2).company("445790")
    assert len(s.requests) == 3       # first try plus two retries, then stop
    assert exc.value.retry_after == 3


def test_429_with_reset_beyond_max_wait_raises_without_sleeping(clock):
    limited = reply("ch_company", status=429, body={},
                    headers={"x-ratelimit-reset": str(int(clock.now() + 99999))})
    s = Script(limited)
    with pytest.raises(RateLimited):
        client(s, clock, max_wait=60).company("445790")
    assert clock.slept == [] and len(s.requests) == 1


@pytest.mark.parametrize("status", [502, 503, 504])
def test_5xx_retried_then_succeeds(clock, status):
    s = Script(reply("ch_company", status=status, body={}), reply("ch_company"))
    assert client(s, clock).company("445790")["company_number"] == "00445790"
    assert len(s.requests) == 2 and len(clock.slept) == 1


def test_5xx_bounded_then_api_error(clock):
    s = Script(reply("ch_company", status=503, body={}))
    with pytest.raises(APIError) as exc:
        client(s, clock, max_retries=2).company("445790")
    assert exc.value.status == 503 and len(s.requests) == 3


def test_404_is_not_found(clock):
    s = Script(reply("ch_not_found"))
    with pytest.raises(NotFound):
        client(s, clock).company("99999999")
    assert len(s.requests) == 1


def test_401_is_auth_error_with_basic_auth_hint(clock):
    s = Script(reply("ch_unauthorized"))
    with pytest.raises(AuthError) as exc:
        client(s, clock).company("445790")
    msg = str(exc.value)
    assert "Basic" in msg and "REST" in msg and "empty password" in msg
    assert exc.value.status == 401


def test_other_4xx_is_api_error_with_message(clock):
    s = Script(reply("ch_company", status=400, body={"error": "bad thing"}))
    with pytest.raises(APIError) as exc:
        client(s, clock).company("445790")
    assert "bad thing" in str(exc.value)


def test_rate_limit_state_is_exposed(clock):
    s = Script(reply("ch_company"))
    c = client(s, clock)
    c.company("445790")
    headers = load("ch_company")["headers"]
    assert c.rate_limit.remaining == int(headers["x-ratelimit-remain"])
    assert c.rate_limit.limit == int(headers["x-ratelimit-limit"])


def test_empty_key_fails_locally_with_hint(clock):
    s = Script(reply("ch_company"))
    with pytest.raises(AuthError) as exc:
        CompaniesHouse("", transport=s.transport)
    assert "Basic" in str(exc.value) and s.requests == []
