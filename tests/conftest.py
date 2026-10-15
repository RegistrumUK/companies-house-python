"""Shared helpers. Fixtures in tests/fixtures/ are REAL captured responses
(scripts/capture_fixtures.py); tests may override status or headers on top of them
(for example, a 429 built from a real response's rate-limit headers) but never invent
a body for the success path."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def reply(name: str, *, status: int | None = None, headers: dict | None = None,
          body=None) -> httpx.Response:
    """Build an httpx.Response from a captured fixture, with optional overrides."""
    rec = load(name)
    merged = dict(rec["headers"])
    merged.update(headers or {})
    return httpx.Response(status or rec["status"], headers=merged,
                          json=rec["body"] if body is None else body)


class FakeClock:
    """Injectable clock and sleep. sleep() advances time instead of waiting."""

    def __init__(self, start: float = 1_792_081_700.0):
        self.t = start
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


class Script:
    """A MockTransport that answers from a list of responses, in order (the last one
    repeats), and records every request it saw."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
