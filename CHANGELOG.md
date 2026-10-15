# Changelog

## 0.2.0 - 2026-10-15

First release on PyPI. Same code as the unpublished 0.1.0. The `companies-house` name
once belonged to a different, since-deleted project (previsedigital/companies_house, versions
0.1.0-0.1.2, 2018), and PyPI never allows a deleted filename to be reused, so this line
starts at 0.2.0.

## 0.1.0 / 0.1.1 - never published

- `CompaniesHouse`: company, search, officers, psc, filing_history, charges, and `iter_*` paging helpers.
- Rate-limit handling: pre-emptive wait on low `X-Ratelimit-Remain`, bounded 429 retries honouring `Retry-After` / `X-Ratelimit-Reset`, bounded retry of 502/503/504.
- `Registrum`: company, search, financials, psc_chain, bundle, and `start_trial(email)`.
- Exceptions: `NotFound`, `AuthError`, `TrialUnverified`, `RateLimited`, `APIError`.
