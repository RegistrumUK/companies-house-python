from __future__ import annotations

import pytest
from conftest import Script, load, reply

from companies_house import (
    APIError,
    AuthError,
    NotFound,
    RateLimited,
    Registrum,
    TrialUnverified,
    __version__,
)

UA = (f"companies-house-python/{__version__} "
      "(+https://github.com/RegistrumUK/companies-house-python)")


def client(script, clock, key="reg_test", **kw):
    return Registrum(key, transport=script.transport, clock=clock.now, sleep=clock.sleep, **kw)


def test_header_and_user_agent_and_host(clock):
    s = Script(reply("reg_company"))
    client(s, clock).company("445790")
    r = s.requests[0]
    assert r.headers["x-api-key"] == "reg_test"
    assert r.headers["user-agent"] == UA
    assert str(r.url) == "https://api.registrum.co.uk/v1/company/00445790"


def test_company_unwraps_data_envelope(clock):
    s = Script(reply("reg_company"))
    assert client(s, clock).company("445790") == load("reg_company")["body"]["data"]


def test_search_financials_psc_chain_bundle_paths(clock):
    s = Script(reply("reg_search"), reply("reg_financials"), reply("reg_psc_chain"),
               reply("reg_bundle"))
    c = client(s, clock)
    c.search("tesco", items_per_page=2)
    fin = c.financials("445790")
    c.psc_chain("445790", max_depth=2)
    c.bundle("445790", include=["profile", "financials"])
    assert [r.url.path for r in s.requests] == [
        "/v1/search", "/v1/company/00445790/financials",
        "/v1/company/00445790/psc/chain", "/v1/company/00445790/bundle"]
    assert s.requests[0].url.params["q"] == "tesco"
    assert s.requests[2].url.params["max_depth"] == "2"
    assert s.requests[3].url.params["include"] == "profile,financials"
    assert fin["company_number"] == "00445790"


def test_key_read_from_environment(clock, monkeypatch):
    monkeypatch.setenv("REGISTRUM_API_KEY", "reg_env")
    s = Script(reply("reg_company"))
    Registrum(transport=s.transport, clock=clock.now, sleep=clock.sleep).company("445790")
    assert s.requests[0].headers["x-api-key"] == "reg_env"


def test_no_key_fails_locally_with_trial_hint(clock, monkeypatch):
    monkeypatch.delenv("REGISTRUM_API_KEY", raising=False)
    s = Script(reply("reg_company"))
    with pytest.raises(AuthError) as exc:
        Registrum(transport=s.transport).company("445790")
    assert "start_trial" in str(exc.value) and s.requests == []


def test_404_and_401(clock):
    with pytest.raises(NotFound):
        client(Script(reply("reg_not_found")), clock).company("99999999")
    with pytest.raises(AuthError):
        client(Script(reply("reg_unauthorized")), clock).company("445790")


def test_403_trial_unverified_has_clear_message(clock):
    # Body shape taken from ch-enrichment-api src/api/middleware.py (TRIAL_UNVERIFIED);
    # an unverified key cannot be captured without minting a real trial.
    body = {"status": "error", "error_code": "TRIAL_UNVERIFIED",
            "detail": "Confirm your email first: click the link we sent to e***@x.com. "
                      "No email? Re-save your Registrum credential to get a new link."}
    s = Script(reply("reg_company", status=403, body=body))
    with pytest.raises(TrialUnverified) as exc:
        client(s, clock).company("445790")
    assert "click the link" in str(exc.value) and "email" in str(exc.value)
    assert isinstance(exc.value, AuthError)


def test_exhausted_quota_with_distant_reset_does_not_sleep(clock):
    # The captured demo-key headers really do say remaining 0, reset next month.
    s = Script(reply("reg_company"), reply("reg_company"))
    c = client(s, clock)
    c.company("445790")
    c.company("445790")
    assert clock.slept == []


def test_429_retry_after_then_success(clock):
    s = Script(reply("reg_company", status=429, headers={"retry-after": "4"},
                     body={"status": "error", "detail": "slow down"}),
               reply("reg_company"))
    client(s, clock).company("445790")
    assert 4 <= clock.slept[0] <= 6


def test_429_distant_reset_raises(clock):
    s = Script(reply("reg_company", status=429, headers={"retry-after": "86400"},
                     body={"status": "error", "detail": "quota"}))
    with pytest.raises(RateLimited) as exc:
        client(s, clock).company("445790")
    assert exc.value.retry_after == 86400 and clock.slept == []


def test_start_trial_posts_email_and_pypi_source(clock, monkeypatch):
    monkeypatch.delenv("REGISTRUM_API_KEY", raising=False)
    created = {"status": "pending_verification", "api_key": "reg_new", "plan": "trial",
               "trial_expires_at": None, "email": "m***@example.com"}
    s = Script(reply("reg_company", status=201, body=created))
    c = Registrum(transport=s.transport, clock=clock.now, sleep=clock.sleep)
    out = c.start_trial("me@example.com")
    r = s.requests[0]
    assert r.method == "POST" and r.url.path == "/v1/trial"
    assert r.read() == b'{"email":"me@example.com","source":"pypi"}'
    assert "x-api-key" not in r.headers
    assert out["api_key"] == "reg_new"
    assert c.api_key == "reg_new"       # the client is usable once the link is clicked


def test_start_trial_conflict_surfaces_server_message(clock, monkeypatch):
    monkeypatch.delenv("REGISTRUM_API_KEY", raising=False)
    s = Script(reply("reg_company", status=409, body={"detail": "This email already has a key."}))
    c = Registrum(transport=s.transport, clock=clock.now, sleep=clock.sleep)
    with pytest.raises(APIError) as exc:
        c.start_trial("a@b.co")
    assert exc.value.status == 409 and "already has a key" in str(exc.value)
