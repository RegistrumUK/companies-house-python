"""Opt-in: hits both real APIs once. Skipped unless CH_API_KEY and REGISTRUM_API_KEY are set."""
import os

import pytest

from companies_house import CompaniesHouse, Registrum

pytestmark = pytest.mark.skipif(
    not (os.environ.get("CH_API_KEY") and os.environ.get("REGISTRUM_API_KEY")),
    reason="set CH_API_KEY and REGISTRUM_API_KEY to run live tests",
)


def test_live_both_apis():
    with CompaniesHouse(os.environ["CH_API_KEY"]) as ch:
        assert ch.company("445790")["company_name"] == "TESCO PLC"
        assert ch.rate_limit.remaining is not None
    with Registrum(os.environ["REGISTRUM_API_KEY"]) as reg:
        assert reg.company("445790")["company_number"] == "00445790"
