# Changelog

## 0.1.0 - 2026-10-15

- `CompaniesHouse`: company, search, officers, psc, filing_history, charges, and `iter_*` paging helpers.
- Rate-limit handling: pre-emptive wait on low `X-Ratelimit-Remain`, bounded 429 retries honouring `Retry-After` / `X-Ratelimit-Reset`, bounded retry of 502/503/504.
- `Registrum`: company, search, financials, psc_chain, bundle, and `start_trial(email)`.
- Exceptions: `NotFound`, `AuthError`, `TrialUnverified`, `RateLimited`, `APIError`.
