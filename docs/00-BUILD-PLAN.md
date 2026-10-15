# Build plan

## Why
Every Companies House package on PyPI together gets roughly 100-150 downloads a month (measured
2026-10-15; ch-api, chwrapper, companies-house-mcp). None handles the rate limit properly and none
returns financials or ownership chains. Goal: be the maintained choice for "companies house api
python" and give an in-place upgrade to Registrum. Parent: RegistrumUK/registrum-website#183 item 4.

## Architecture
- `_http.Transport`: one httpx client, auth, User-Agent, rate-limit state, bounded retries, injectable
  clock and sleep. Shared by both clients.
- `CompaniesHouse`: official REST API, HTTP Basic (key as username, empty password).
- `Registrum`: https://api.registrum.co.uk, `X-API-Key`; unwraps the `data` envelope; `start_trial`.
- Rate limiting: sleep to reset when remaining <= low_watermark and the wait is <= max_wait; on 429
  honour Retry-After or the reset header, bounded; retry 502/503/504 with backoff.
- Both APIs report `X-Ratelimit-Reset` as epoch seconds. CH sends `-Remain`, Registrum `-Remaining`.

## Backlog
- v0.1.0: this build (#1). Release (#2) waits on Eugene's PyPI trusted-publisher setup.
- Later, only on demand: async client, typed models, more Registrum endpoints, caching.
